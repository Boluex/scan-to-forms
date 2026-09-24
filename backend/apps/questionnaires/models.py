from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class Questionnaire(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        READY = "READY", "Ready"
        ARCHIVED = "ARCHIVED", "Archived"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="questionnaires")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    source_language = models.CharField(max_length=12, default="en")

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title


class QuestionnaireVersion(TimeStampedModel):
    class ParseStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        VALID = "VALID", "Valid"
        NEEDS_REVIEW = "NEEDS_REVIEW", "Needs review"

    questionnaire = models.ForeignKey(Questionnaire, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    parse_status = models.CharField(max_length=20, choices=ParseStatus.choices, default=ParseStatus.DRAFT)
    parser_version = models.CharField(max_length=80, blank=True)
    raw_schema = models.JSONField(default=dict, blank=True)
    expected_page_count = models.PositiveIntegerField(
        default=1,
        validators=(MinValueValidator(1), MaxValueValidator(100)),
        help_text="Number of physical pages in one complete questionnaire response.",
    )

    class Meta:
        ordering = ("-version_number",)
        constraints = [
            models.UniqueConstraint(fields=("questionnaire", "version_number"), name="unique_questionnaire_version")
        ]

    def __str__(self):
        return f"{self.questionnaire.title} v{self.version_number}"


class TemplatePage(TimeStampedModel):
    version = models.ForeignKey(QuestionnaireVersion, on_delete=models.CASCADE, related_name="template_pages")
    page_number = models.PositiveIntegerField(validators=(MinValueValidator(1), MaxValueValidator(100)))
    reference_text = models.TextField(blank=True)
    anchors = models.JSONField(default=list, blank=True)
    text_signature = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ("page_number",)
        constraints = [
            models.UniqueConstraint(fields=("version", "page_number"), name="unique_template_page_per_version")
        ]

    def __str__(self):
        return f"{self.version} page {self.page_number}"


class Question(TimeStampedModel):
    class Type(models.TextChoices):
        SHORT_TEXT = "SHORT_TEXT", "Short answer"
        PARAGRAPH = "PARAGRAPH", "Paragraph"
        SINGLE_CHOICE = "SINGLE_CHOICE", "Single choice"
        MULTIPLE_CHOICE = "MULTIPLE_CHOICE", "Multiple choice"
        DROPDOWN = "DROPDOWN", "Dropdown"
        LIKERT = "LIKERT", "Likert scale"
        LINEAR_SCALE = "LINEAR_SCALE", "Linear scale"
        SINGLE_GRID = "SINGLE_GRID", "Multiple-choice grid"
        MULTIPLE_GRID = "MULTIPLE_GRID", "Checkbox grid"
        DATE = "DATE", "Date"
        TIME = "TIME", "Time"
        NUMBER = "NUMBER", "Number"

    version = models.ForeignKey(QuestionnaireVersion, on_delete=models.CASCADE, related_name="questions")
    key = models.CharField(max_length=80)
    position = models.PositiveIntegerField()
    text = models.TextField()
    help_text = models.TextField(blank=True)
    type = models.CharField(max_length=24, choices=Type.choices)
    required = models.BooleanField(default=False)
    validation_rules = models.JSONField(default=dict, blank=True)
    source_region = models.JSONField(default=dict, blank=True)
    template_page_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=(MinValueValidator(1), MaxValueValidator(100)),
    )

    class Meta:
        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(fields=("version", "key"), name="unique_question_key_per_version"),
            models.UniqueConstraint(fields=("version", "position"), name="unique_question_position_per_version"),
        ]

    def __str__(self):
        return self.text[:80]


class QuestionOption(TimeStampedModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    key = models.CharField(max_length=80)
    label = models.CharField(max_length=500)
    position = models.PositiveIntegerField()
    value = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(fields=("question", "key"), name="unique_option_key_per_question"),
            models.UniqueConstraint(fields=("question", "position"), name="unique_option_position_per_question"),
        ]

    def save(self, *args, **kwargs):
        if not self.value:
            self.value = self.label
        super().save(*args, **kwargs)


class ResponseBatch(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PROCESSING = "PROCESSING", "Processing"
        NEEDS_REVIEW = "NEEDS_REVIEW", "Needs review"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="response_batches")
    questionnaire_version = models.ForeignKey(QuestionnaireVersion, on_delete=models.PROTECT, related_name="batches")
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)

    class Meta:
        ordering = ("-created_at",)


class Response(TimeStampedModel):
    class Status(models.TextChoices):
        UPLOADING = "UPLOADING", "Uploading"
        INCOMPLETE = "INCOMPLETE", "Incomplete"
        READY_FOR_PROCESSING = "READY_FOR_PROCESSING", "Ready for processing"
        PROCESSING = "PROCESSING", "Processing"
        NEEDS_REVIEW = "NEEDS_REVIEW", "Needs review"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"
        FAILED = "FAILED", "Failed"

    batch = models.ForeignKey(ResponseBatch, on_delete=models.CASCADE, related_name="responses")
    sequence = models.PositiveIntegerField(null=True, blank=True)
    respondent_reference = models.CharField(max_length=120, blank=True)
    expected_page_count = models.PositiveIntegerField(default=1, validators=(MinValueValidator(1), MaxValueValidator(100)))
    validation_issues = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.UPLOADING, db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_responses"
    )

    class Meta:
        ordering = ("sequence", "created_at")
        constraints = [
            models.UniqueConstraint(fields=("batch", "sequence"), name="unique_response_sequence_per_batch"),
            models.CheckConstraint(condition=(models.Q(status="CONFIRMED", confirmed_at__isnull=False) | (~models.Q(status="CONFIRMED") & models.Q(confirmed_at__isnull=True))), name="response_confirmation_consistent"),
        ]


class Answer(TimeStampedModel):
    class Provenance(models.TextChoices):
        OCR = "OCR", "OCR"
        MANUAL = "MANUAL", "Human correction"
        APPROVED = "APPROVED", "Human approved"

    provenance = models.CharField(max_length=12, choices=Provenance.choices, default=Provenance.OCR)

    class ReviewStatus(models.TextChoices):
        AUTO_HIGH = "AUTO_HIGH", "High confidence"
        AUTO_MEDIUM = "AUTO_MEDIUM", "Medium confidence"
        NEEDS_REVIEW = "NEEDS_REVIEW", "Needs review"
        CORRECTED = "CORRECTED", "Corrected"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="answers")
    value_text = models.TextField(blank=True)
    value_json = models.JSONField(default=dict, blank=True)
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        validators=(MinValueValidator(0), MaxValueValidator(1)),
    )
    review_status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.NEEDS_REVIEW)
    source_region = models.JSONField(default=dict, blank=True)
    raw_value = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("question__position",)
        constraints = [models.UniqueConstraint(fields=("response", "question"), name="unique_answer_per_response_question")]
