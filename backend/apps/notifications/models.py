from django.conf import settings
from django.db import models

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

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=40, choices=Kind.choices, db_index=True)
    title = models.CharField(max_length=180)
    message = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("user", "read_at"))]

