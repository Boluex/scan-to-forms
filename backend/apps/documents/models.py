import uuid
from pathlib import Path

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


def secure_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"questionnaires/{instance.owner_id}/{uuid.uuid4().hex}{extension}"


class UploadedDocument(TimeStampedModel):
    class Type(models.TextChoices):
        TEMPLATE = "TEMPLATE", "Blank questionnaire template"
        RESPONSE = "RESPONSE", "Completed questionnaire"

    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "Uploaded"
        QUEUED = "QUEUED", "Queued"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        NEEDS_REVIEW = "NEEDS_REVIEW", "Needs review"
        FAILED = "FAILED", "Failed"
        DELETED = "DELETED", "Deleted"

    class GroupingMode(models.TextChoices):
        PDF_PER_RESPONSE = "PDF_PER_RESPONSE", "One PDF per respondent"
        MANUAL_RESPONSE = "MANUAL_RESPONSE", "Manual respondent pages"
        BULK_ORDERED = "BULK_ORDERED", "Bulk images in respondent order"
        TEMPLATE = "TEMPLATE", "Questionnaire template"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="uploaded_documents")
    questionnaire = models.ForeignKey(
        "questionnaires.Questionnaire", null=True, blank=True, on_delete=models.CASCADE, related_name="documents"
    )
    batch = models.ForeignKey(
        "questionnaires.ResponseBatch", null=True, blank=True, on_delete=models.CASCADE, related_name="documents"
    )
    response = models.ForeignKey(
        "questionnaires.Response", null=True, blank=True, on_delete=models.SET_NULL, related_name="documents"
    )
    document_type = models.CharField(max_length=20, choices=Type.choices)
    file = models.FileField(upload_to=secure_upload_path, max_length=500)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    page_count = models.PositiveIntegerField(default=1)
    grouping_mode = models.CharField(max_length=24, choices=GroupingMode.choices, default=GroupingMode.PDF_PER_RESPONSE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED, db_index=True)
    failure_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("owner", "sha256"))]


class DocumentPage(TimeStampedModel):
    class ProcessingStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    class ClassificationMethod(models.TextChoices):
        UNCLASSIFIED = "UNCLASSIFIED", "Unclassified"
        UPLOAD_ORDER = "UPLOAD_ORDER", "Provisional upload order"
        PAGE_MARKER = "PAGE_MARKER", "Printed page marker"
        TEXT_SIMILARITY = "TEXT_SIMILARITY", "Template text similarity"
        MANUAL = "MANUAL", "Manual assignment"
        QR_CODE = "QR_CODE", "QR code"

    document = models.ForeignKey(UploadedDocument, on_delete=models.CASCADE, related_name="pages")
    response = models.ForeignKey(
        "questionnaires.Response",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="pages",
    )
    page_number = models.PositiveIntegerField()
    original_upload_order = models.PositiveIntegerField(default=1)
    detected_template_page_number = models.PositiveIntegerField(null=True, blank=True)
    assigned_template_page_number = models.PositiveIntegerField(null=True, blank=True)
    classification_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        validators=(MinValueValidator(0), MaxValueValidator(1)),
    )
    classification_method = models.CharField(
        max_length=24,
        choices=ClassificationMethod.choices,
        default=ClassificationMethod.UNCLASSIFIED,
    )
    processing_status = models.CharField(
        max_length=16,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    validation_issues = models.JSONField(default=list, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    preprocessing = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("assigned_template_page_number", "original_upload_order", "page_number")
        constraints = [models.UniqueConstraint(fields=("document", "page_number"), name="unique_document_page")]
        indexes = [models.Index(fields=("response", "assigned_template_page_number"))]


class OCRJob(TimeStampedModel):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        NEEDS_REVIEW = "NEEDS_REVIEW", "Needs review"

    document = models.OneToOneField(UploadedDocument, on_delete=models.CASCADE, related_name="ocr_job")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    engine = models.CharField(max_length=80, blank=True)
    model_version = models.CharField(max_length=120, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    processing_ms = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)


class OCRResult(TimeStampedModel):
    job = models.ForeignKey(OCRJob, on_delete=models.CASCADE, related_name="results")
    page = models.ForeignKey(DocumentPage, on_delete=models.CASCADE, related_name="ocr_results")
    plain_text = models.TextField(blank=True)
    mean_confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    raw_output = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("job", "page"), name="unique_ocr_result_per_job_page")]


class OCRRegion(TimeStampedModel):
    result = models.ForeignKey(OCRResult, on_delete=models.CASCADE, related_name="regions")
    sequence = models.PositiveIntegerField()
    kind = models.CharField(max_length=40, default="text")
    text = models.TextField(blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    bounding_box = models.JSONField(default=dict)

    class Meta:
        ordering = ("sequence",)
        constraints = [models.UniqueConstraint(fields=("result", "sequence"), name="unique_ocr_region_sequence")]


class ExtractionResult(TimeStampedModel):
    job = models.OneToOneField(OCRJob, on_delete=models.CASCADE, related_name="extraction")
    parser_version = models.CharField(max_length=80)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    structured_output = models.JSONField(default=dict, blank=True)
    warnings = models.JSONField(default=list, blank=True)
