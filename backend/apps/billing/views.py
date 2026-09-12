import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import generics, permissions, status, views
from rest_framework import serializers as drf_serializers
from rest_framework.response import Response

from .gateway import (
    apply_subscription_event,
    event_payload_hash,
    fulfill_known_transaction,
    fulfill_recurring_charge,
)
from .models import PaymentTransaction, PaystackEvent, Plan
from .paystack import PaystackClient, configured_plan_code
from .serializers import (
    CheckoutSerializer,
    PaymentTransactionSerializer,
    PaystackWebhookSerializer,
    PlanSerializer,
    VerifyPaymentSerializer,
)
from .services import entitlements_for, usage_for


class PlanListView(generics.ListAPIView):
    serializer_class = PlanSerializer
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    pagination_class = None

    def get_queryset(self):
        return Plan.objects.filter(is_public=True)


class BillingSummaryView(views.APIView):
    @extend_schema(
        responses=inline_serializer(
            name="BillingSummaryResponse",
            fields={
                "plan": PlanSerializer(),
                "subscription": drf_serializers.JSONField(allow_null=True),
                "usage": drf_serializers.JSONField(),
                "is_organization_member": drf_serializers.BooleanField(),
                "paystack_configured": drf_serializers.BooleanField(),
                "admin_contact_email": drf_serializers.EmailField(),
            },
        )
    )
    def get(self, request):
        entitlements, usage = usage_for(request.user)
        plan = entitlements.plan
        subscription = entitlements.subscription
        return Response(
            {
                "plan": PlanSerializer(plan).data,
                "subscription": {
                    "status": subscription.status,
                    "billing_cycle": subscription.billing_cycle,
                    "current_period_end": subscription.current_period_end,
                    "cancel_at_period_end": subscription.cancel_at_period_end,
                }
                if subscription
                else None,
                "usage": {
                    "month": usage.month,
                    "pages_used": usage.pages_used,
                    "included_pages": plan.monthly_page_limit,
                    "extra_pages": usage.extra_pages,
                    "pages_remaining": max(plan.monthly_page_limit + usage.extra_pages - usage.pages_used, 0),
                    "bot_lab_runs_used": usage.bot_lab_runs_used,
                    "bot_lab_runs_included": plan.monthly_bot_lab_runs,
                },
                "is_organization_member": entitlements.account != request.user,
                "paystack_configured": bool(settings.PAYSTACK_SECRET_KEY),
                "admin_contact_email": settings.ADMIN_CONTACT_EMAIL,
            }
        )


class CheckoutView(generics.GenericAPIView):
    serializer_class = CheckoutSerializer

    @transaction.atomic
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data["product"]
        plan = None
        cycle = ""
        paystack_plan = ""
        if product == PaymentTransaction.Product.EXTRA_PAGES:
            amount_kobo = settings.EXTRA_OCR_PAGES_PRICE_KOBO
        else:
            plan = Plan.objects.get(code=serializer.validated_data["plan_code"])
            if plan.contact_required:
                return Response(
                    {"detail": "Organization plans are arranged by the administrator for up to 10 people."},
                    status=status.HTTP_409_CONFLICT,
                )
            cycle = serializer.validated_data["billing_cycle"]
            amount_kobo = plan.yearly_price_kobo if cycle == "YEARLY" else plan.monthly_price_kobo
            paystack_plan = configured_plan_code(plan.code, cycle)
        reference = f"STF-{uuid.uuid4().hex}"
        payment = PaymentTransaction.objects.create(
            user=request.user,
            plan=plan,
            product=product,
            billing_cycle=cycle,
            reference=reference,
            amount_kobo=amount_kobo,
        )
        payload = {
            "email": request.user.email,
            "amount": str(amount_kobo),
            "currency": "NGN",
            "reference": reference,
            "callback_url": settings.PAYSTACK_CALLBACK_URL,
            "metadata": json.dumps({"payment_id": str(payment.id), "product": product}),
        }
        if paystack_plan:
            payload["plan"] = paystack_plan
        initialized = PaystackClient().initialize_transaction(payload)
        payment.authorization_url = initialized["authorization_url"]
        payment.access_code = initialized["access_code"]
        payment.save(update_fields=("authorization_url", "access_code", "updated_at"))
        return Response(PaymentTransactionSerializer(payment).data, status=status.HTTP_201_CREATED)


class VerifyPaymentView(generics.GenericAPIView):
    serializer_class = VerifyPaymentSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = generics.get_object_or_404(
            PaymentTransaction,
            reference=serializer.validated_data["reference"],
            user=request.user,
        )
        gateway_data = PaystackClient().verify_transaction(payment.reference)
        payment = fulfill_known_transaction(payment, gateway_data, request=request)
        if payment.status != PaymentTransaction.Status.SUCCESS:
            return Response({"detail": "Payment was not verified."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PaymentTransactionSerializer(payment).data)


class PaymentHistoryView(generics.ListAPIView):
    serializer_class = PaymentTransactionSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PaymentTransaction.objects.none()
        return PaymentTransaction.objects.filter(user=self.request.user).select_related("plan")


class SubscriptionManageView(views.APIView):
    @extend_schema(
        request=None,
        responses=inline_serializer(
            name="SubscriptionManageResponse",
            fields={"url": drf_serializers.URLField()},
        ),
    )
    def post(self, request):
        entitlements = entitlements_for(request.user)
        subscription = entitlements.subscription
        if not subscription or not subscription.paystack_subscription_code:
            return Response(
                {"detail": "This subscription is not managed automatically by Paystack. Contact the administrator."},
                status=status.HTTP_409_CONFLICT,
            )
        data = PaystackClient().subscription_manage_link(subscription.paystack_subscription_code)
        return Response({"url": data.get("link")})


class PaystackWebhookView(views.APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = ()

    @extend_schema(
        request=PaystackWebhookSerializer,
        responses={
            200: OpenApiResponse(description="Event accepted."),
            400: OpenApiResponse(description="Malformed event."),
            401: OpenApiResponse(description="Invalid Paystack signature."),
        },
    )
    @transaction.atomic
    def post(self, request):
        raw_body = request.body
        supplied = request.headers.get("x-paystack-signature", "")
        expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw_body, hashlib.sha512).hexdigest()
        if not settings.PAYSTACK_SECRET_KEY or not hmac.compare_digest(supplied, expected):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = json.loads(raw_body)
        except ValueError:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        digest = event_payload_hash(raw_body)
        _, created = PaystackEvent.objects.get_or_create(payload_hash=digest, defaults={"event_type": payload.get("event", "")})
        if not created:
            return Response(status=status.HTTP_200_OK)
        event_type = payload.get("event", "")
        data = payload.get("data") or {}
        if event_type == "charge.success":
            reference = data.get("reference", "")
            payment = PaymentTransaction.objects.filter(reference=reference).first()
            if payment:
                fulfill_known_transaction(payment, data)
            else:
                fulfill_recurring_charge(data)
        elif event_type in {
            "subscription.create",
            "subscription.not_renew",
            "subscription.disable",
            "invoice.payment_failed",
        }:
            apply_subscription_event(event_type, data)
        return Response(status=status.HTTP_200_OK)
