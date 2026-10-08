from django.db import transaction
from django.db.models import Count
from rest_framework import decorators, filters, permissions, serializers, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import AuditLog, record_audit
from apps.notifications.models import Notification, PushDelivery
from apps.orders.models import Order

from .models import User


class AdministratorPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user.is_authenticated
            and user.is_staff
            and (user.is_superuser or user.role == User.Role.ADMIN)
        )


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "name",
            "institution",
            "role",
            "is_staff",
            "is_superuser",
            "is_active",
            "account_status",
            "date_joined",
        )
        read_only_fields = fields


class UserControlSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=["suspend", "reactivate", "grant_operator", "revoke_operator"]
    )


class AdminUsersViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (AdministratorPermission,)
    serializer_class = AdminUserSerializer
    queryset = User.objects.order_by("-date_joined")
    filter_backends = (filters.SearchFilter,)
    search_fields = ("email", "name", "institution")

    @decorators.action(detail=True, methods=["post"])
    @transaction.atomic
    def control(self, request, pk=None):
        serializer = UserControlSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        user = User.objects.select_for_update().get(pk=self.get_object().pk)
        if user.pk == request.user.pk or user.is_superuser:
            return Response(
                {"detail": "You cannot change yourself or a superuser here."}, status=403
            )
        if (
            user.is_staff or action in ("grant_operator", "revoke_operator")
        ) and not request.user.is_superuser:
            return Response({"detail": "Only a superuser can manage operator access."}, status=403)
        if action == "suspend":
            user.account_status = User.AccountStatus.SUSPENDED
            user.is_active = False
            user.push_devices.update(active=False)
        elif action == "reactivate":
            user.account_status = (
                User.AccountStatus.ACTIVE if user.email_verified_at else User.AccountStatus.PENDING
            )
            user.is_active = True
        else:
            user.is_staff = action == "grant_operator"
            # Operator access grants order tools, not administrator privileges.
            if action == "revoke_operator" and user.role == User.Role.ADMIN:
                user.role = User.Role.USER
        user.save(update_fields=["account_status", "is_active", "is_staff", "role"])
        record_audit(
            actor=request.user, action=f"admin.user.{action}", target=user, request=request
        )
        return Response(self.get_serializer(user).data)


class AnnouncementSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=180)
    message = serializers.CharField(max_length=2000)


class AnnouncementView(APIView):
    permission_classes = (AdministratorPermission,)

    @transaction.atomic
    def post(self, request):
        serializer = AnnouncementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = 0
        # Use create so each recipient gets its durable push outbox entries.
        for user in (
            User.objects.filter(is_active=True)
            .exclude(account_status__in=["SUSPENDED", "DEACTIVATED"])
            .iterator()
        ):
            Notification.objects.create(
                user=user, kind=Notification.Kind.SYSTEM, **serializer.validated_data
            )
            count += 1
        record_audit(
            actor=request.user,
            action="admin.announcement",
            request=request,
            metadata={"title": serializer.validated_data["title"], "recipients": count},
        )
        return Response(
            {
                "recipients": count,
                "detail": "Announcement saved to inboxes. Push delivery is queued for opted-in devices.",
            },
            status=201,
        )


class AdminOverviewView(APIView):
    permission_classes = (AdministratorPermission,)

    def get(self, request):
        return Response(
            {
                "users": User.objects.count(),
                "active_users": User.objects.filter(is_active=True).count(),
                "orders": Order.objects.count(),
                "payment_pending": Order.objects.filter(payment_status="SUBMITTED").count(),
                "orders_by_status": dict(
                    Order.objects.values_list("status").annotate(total=Count("id"))
                ),
                "push_pending": PushDelivery.objects.filter(
                    sent_at__isnull=True, attempts__lt=8
                ).count(),
                "push_failed": PushDelivery.objects.filter(
                    sent_at__isnull=True, attempts__gte=8
                ).count(),
                "recent_activity": list(
                    AuditLog.objects.select_related("actor").values(
                        "id", "action", "actor__email", "created_at"
                    )[:12]
                ),
            }
        )
