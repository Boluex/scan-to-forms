from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ExportJob(TimeStampedModel):
    class Format(models.TextChoices):
        CSV = "CSV", "CSV"
        XLSX = "XLSX", "Excel XLSX"

    class Status(models.TextChoices):
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="export_jobs")
    batch = models.ForeignKey("questionnaires.ResponseBatch", on_delete=models.CASCADE, related_name="export_jobs")
    format = models.CharField(max_length=8, choices=Format.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    response_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

