from django.utils import timezone
from rest_framework import decorators, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user)

    @decorators.action(detail=False, methods=("get",), url_path="unread-count")
    def unread_count(self, request):
        return Response({"count": self.get_queryset().filter(read_at__isnull=True).count()})

    @decorators.action(detail=True, methods=("post",), url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=("read_at", "updated_at"))
        return Response(self.get_serializer(notification).data)

    @decorators.action(detail=False, methods=("post",), url_path="mark-all-read")
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"updated": updated})


class PushDeviceView(APIView):
    def post(self, request):
        from django.conf import settings

        from .models import PushDevice
        from .serializers import PushTokenSerializer

        if not settings.FIREBASE_PUSH_ENABLED:
            return Response({"detail": "Push notifications are not configured yet."}, status=503)
        serializer = PushTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PushDevice.objects.update_or_create(
            token=serializer.validated_data["token"],
            defaults={
                "user": request.user,
                "active": True,
                "label": serializer.validated_data.get("label", ""),
            },
        )
        return Response({"detail": "Notifications enabled on this device."})

    def delete(self, request):
        from .models import PushDevice
        from .serializers import PushTokenSerializer

        serializer = PushTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PushDevice.objects.filter(
            user=request.user, token=serializer.validated_data["token"]
        ).update(active=False)
        return Response(status=204)
