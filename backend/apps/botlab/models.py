from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class BotRun(TimeStampedModel):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bot_runs")
    questionnaire_version = models.ForeignKey(
        "questionnaires.QuestionnaireVersion", on_delete=models.CASCADE, related_name="bot_runs"
    )
    requested_responses = models.PositiveIntegerField()
    generated_responses = models.PositiveIntegerField(default=0)
    seed = models.PositiveBigIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)


class SyntheticResponse(TimeStampedModel):
    run = models.ForeignKey(BotRun, on_delete=models.CASCADE, related_name="responses")
    sequence = models.PositiveIntegerField()
    answers = models.JSONField(default=dict)
    data_label = models.CharField(max_length=80, default="SYNTHETIC TEST DATA — NOT A HUMAN RESEARCH RESPONSE")

    class Meta:
        ordering = ("sequence",)
        constraints = [models.UniqueConstraint(fields=("run", "sequence"), name="unique_synthetic_run_sequence")]

