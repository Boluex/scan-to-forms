from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class AppsScriptJob(TimeStampedModel):
    class SourceType(models.TextChoices):
        RESPONSE_BATCH = "RESPONSE_BATCH", "Confirmed human responses"
        BOT_RUN = "BOT_RUN", "Bot Lab synthetic responses"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="apps_script_jobs")
    source_type = models.CharField(max_length=24, choices=SourceType.choices)
    batch = models.ForeignKey(
        "questionnaires.ResponseBatch",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="apps_script_jobs",
    )
    bot_run = models.ForeignKey(
        "botlab.BotRun",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="apps_script_jobs",
    )
    questionnaire_version = models.ForeignKey(
        "questionnaires.QuestionnaireVersion",
        on_delete=models.PROTECT,
        related_name="apps_script_jobs",
    )
    form_id = models.CharField(max_length=180)
    mappings = models.JSONField(default=dict)
    script = models.TextField()
    response_count = models.PositiveIntegerField()
    data_classification = models.CharField(max_length=100)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=(Q(batch__isnull=False, bot_run__isnull=True) | Q(batch__isnull=True, bot_run__isnull=False)),
                name="apps_script_exactly_one_source",
            )
        ]

    def __str__(self):
        return f"Apps Script {self.id} for {self.form_id}"

