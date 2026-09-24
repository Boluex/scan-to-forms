import hashlib

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.accounts.models import User
from apps.core.models import record_audit

from .models import PaymentTransaction, Plan, Subscription
from .paystack import plan_for_paystack_code
from .services import activate_subscription, add_extra_pages


def _paid_at(value):
    if not value:
        return timezone.now()
    parsed = parse_datetime(value) if isinstance(value, str) else None
    if parsed:
        return parsed
    return timezone.now()


@transaction.atomic
def fulfill_known_transaction(payment, data, *, request=None):
    payment = PaymentTransaction.objects.select_for_update().select_related("user", "plan").get(pk=payment.pk)
    if payment.status == PaymentTransaction.Status.SUCCESS:
        return payment
    if data.get("status") != "success":
        payment.status = PaymentTransaction.Status.FAILED
        payment.gateway_response = data
        payment.save(update_fields=("status", "gateway_response", "updated_at"))
        return payment
    if int(data.get("amount", -1)) != payment.amount_kobo or str(data.get("currency", "")).upper() != payment.currency:
        payment.status = PaymentTransaction.Status.FAILED
        payment.gateway_response = data
        payment.save(update_fields=("status", "gateway_response", "updated_at"))
        return payment

    payment.status = PaymentTransaction.Status.SUCCESS
    payment.paystack_id = str(data.get("id", ""))
    payment.paid_at = _paid_at(data.get("paid_at"))
    payment.gateway_response = data
    payment.save(
        update_fields=("status", "paystack_id", "paid_at", "gateway_response", "updated_at")
    )
    customer = data.get("customer") or {}
    if payment.product == PaymentTransaction.Product.EXTRA_PAGES:
        add_extra_pages(payment.user, 100)
    else:
        activate_subscription(
            payment.user,
            payment.plan,
            payment.billing_cycle,
            customer_code=customer.get("customer_code", ""),
        )
    record_audit(
        actor=payment.user,
        action="payment.verified",
        target=payment,
        request=request,
        metadata={"product": payment.product, "amount_kobo": payment.amount_kobo},
    )
    return payment


def _plan_code_from_event(data):
    plan = data.get("plan") or {}
    if isinstance(plan, str):
        return plan
    return plan.get("plan_code") or data.get("plan_code") or ""


@transaction.atomic
def fulfill_recurring_charge(data):
    reference = str(data.get("reference", ""))
    if not reference or data.get("status") != "success":
        return None
    existing = PaymentTransaction.objects.filter(reference=reference).first()
    if existing:
        return fulfill_known_transaction(existing, data)
    mapping = plan_for_paystack_code(_plan_code_from_event(data))
    customer = data.get("customer") or {}
    email = str(customer.get("email", "")).lower()
    if not mapping or not email:
        return None
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return None
    plan_code, billing_cycle = mapping
    plan = Plan.objects.get(code=plan_code)
    expected = plan.yearly_price_kobo if billing_cycle == Subscription.BillingCycle.YEARLY else plan.monthly_price_kobo
    if int(data.get("amount", -1)) != expected or str(data.get("currency", "")).upper() != "NGN":
        return None
    payment = PaymentTransaction.objects.create(
        user=user,
        plan=plan,
        product=PaymentTransaction.Product.SUBSCRIPTION,
        billing_cycle=billing_cycle,
        reference=reference,
        amount_kobo=expected,
    )
    return fulfill_known_transaction(payment, data)


def apply_subscription_event(event_type, data):
    subscription_data = data.get("subscription") if isinstance(data.get("subscription"), dict) else data
    subscription_code = subscription_data.get("subscription_code", "")
    customer = data.get("customer") or subscription_data.get("customer") or {}
    email = str(customer.get("email", "")).lower()
    subscription = Subscription.objects.filter(paystack_subscription_code=subscription_code).first() if subscription_code else None
    if not subscription and email:
        subscription = Subscription.objects.filter(user__email__iexact=email).first()
    if event_type == "subscription.create":
        if not subscription and email:
            mapping = plan_for_paystack_code(_plan_code_from_event(subscription_data))
            user = User.objects.filter(email__iexact=email).first()
            if mapping and user:
                plan_code, billing_cycle = mapping
                now = timezone.now()
                subscription = Subscription.objects.create(
                    user=user,
                    plan=Plan.objects.get(code=plan_code),
                    billing_cycle=billing_cycle,
                    status=Subscription.Status.CANCELLED,
                    current_period_start=now,
                    current_period_end=now,
                )
        if not subscription:
            return
        subscription.paystack_subscription_code = subscription_code
        subscription.paystack_email_token = subscription_data.get("email_token", "")
        subscription.paystack_customer_code = customer.get("customer_code", subscription.paystack_customer_code)
        subscription.save(
            update_fields=("paystack_subscription_code", "paystack_email_token", "paystack_customer_code", "updated_at")
        )
    elif not subscription:
        return
    elif event_type == "subscription.not_renew":
        subscription.cancel_at_period_end = True
        subscription.save(update_fields=("cancel_at_period_end", "updated_at"))
    elif event_type == "subscription.disable":
        subscription.status = Subscription.Status.CANCELLED
        subscription.save(update_fields=("status", "updated_at"))
    elif event_type == "invoice.payment_failed":
        subscription.status = Subscription.Status.PAST_DUE
        subscription.save(update_fields=("status", "updated_at"))


def event_payload_hash(raw_body):
    return hashlib.sha256(raw_body).hexdigest()
