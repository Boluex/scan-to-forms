from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Notification(TimeStampedModel):
    class Kind(models.TextChoices):
        PAYMENT_VERIFIED = "PAYMENT_VERIFIED", "Payment verified"
        PROCESSING_STARTED = "PROCESSING_STARTED", "Processing started"
        NEEDS_ATTENTION = "NEEDS_ATTENTION", "Needs attention"
        ORDER_READY = "ORDER_READY", "Order ready"
        PAYMENT_REJECTED = "PAYMENT_REJECTED", "Payment rejected"
        OCR_COMPLETED = "OCR_COMPLETED", "OCR completed"
        OCR_FAILED = "OCR_FAILED", "OCR failed"
        REVIEW_REQUIRED = "REVIEW_REQUIRED", "Review required"
        EXPORT_READY = "EXPORT_READY", "Export ready"
        SYSTEM = "SYSTEM", "System"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=40, choices=Kind.choices, db_index=True)
    title = models.CharField(max_length=180)
    message = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("user", "read_at"))]


class PushDevice(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_devices"
    )
    token = models.CharField(max_length=2048, unique=True)
    label = models.CharField(max_length=120, blank=True)
    active = models.BooleanField(default=True)


class PushDelivery(TimeStampedModel):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    device = models.ForeignKey(PushDevice, on_delete=models.CASCADE)
    attempts = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_error = models.CharField(max_length=80, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("notification", "device"), name="unique_push_delivery")
        ]
