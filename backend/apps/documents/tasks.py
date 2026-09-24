import shutil
import tempfile
import time
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.questionnaires.models import QuestionnaireVersion, Response

from .models import DocumentPage, ExtractionResult, OCRJob, OCRRegion, OCRResult, UploadedDocument
from .services.grouping import (
    aggregate_response_answers,
    classify_page,
    create_document_pages,
    create_response,
    refresh_response_validation,
    update_batch_status,
    update_template_page,
)
from .services.ocr import extract_document
from .services.parser import PARSER_VERSION, detect_schema, persist_detected_schema


def _page_regions(page_output, page):
    values = []
    for region in page_output.regions:
        values.append(
            {
                "text": region.text,
                "confidence": region.confidence,
                "bounding_box": {
                    **region.bounding_box,
                    "document_page_id": str(page.id),
                    "template_page_number": page_output.page_number,
                },
                "template_page_number": page_output.page_number,
            }
        )
    return values


@shared_task(bind=True, autoretry_for=(OSError,), retry_backoff=True, max_retries=2)
def process_document(self, job_id):
    started = time.monotonic()
    job = OCRJob.objects.select_related(
        "document__owner",
        "document__questionnaire",
        "document__batch__questionnaire_version",
        "document__response",
    ).get(pk=job_id)
    document = job.document
    if document.order_id:
        from apps.orders.services import document_started
        document_started(document)
    if job.status == OCRJob.Status.PROCESSING:
        return str(document.id)
    if document.document_type == UploadedDocument.Type.RESPONSE and not document.response_id:
        document.response = create_response(document.batch)
        document.save(update_fields=("response", "updated_at"))
    if not document.pages.exists():
        create_document_pages(document)
    response_id = document.response_id
    job.status = OCRJob.Status.PROCESSING
    job.started_at = timezone.now()
    job.attempts += 1
    job.error_code = ""
    job.error_message = ""
    job.save(update_fields=("status", "started_at", "attempts", "error_code", "error_message", "updated_at"))
    document.status = UploadedDocument.Status.PROCESSING
    document.failure_reason = ""
    document.save(update_fields=("status", "failure_reason", "updated_at"))
    document.pages.update(processing_status=DocumentPage.ProcessingStatus.PROCESSING)
    if response_id:
        Response.objects.filter(pk=response_id).update(
            status=Response.Status.PROCESSING,
            confirmed_at=None,
            reviewed_by=None,
        )

    succeeded = False
    structured = {}
    warnings = []
    confidence = None
    try:
        with tempfile.TemporaryDirectory(prefix="scanforms-ocr-") as directory:
            local_path = Path(directory) / ("input" + Path(document.original_filename).suffix.lower())
            with document.file.open("rb") as source, local_path.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            output = extract_document(local_path, settings.OCR_ENGINE)
        all_regions = []
        confidence_values = []
        processed_page_numbers = set()
        with transaction.atomic():
            job.results.all().delete()
            for page_output in output.pages:
                processed_page_numbers.add(page_output.page_number)
                page, _ = DocumentPage.objects.get_or_create(
                    document=document,
                    page_number=page_output.page_number,
                    defaults={
                        "response_id": response_id,
                        "original_upload_order": page_output.page_number,
                        "assigned_template_page_number": page_output.page_number,
                        "classification_method": DocumentPage.ClassificationMethod.UPLOAD_ORDER,
                        "classification_confidence": 0.55,
                    },
                )
                page.width = page_output.width
                page.height = page_output.height
                page.preprocessing = page_output.preprocessing
                page.processing_status = DocumentPage.ProcessingStatus.COMPLETED
                page.save(update_fields=("width", "height", "preprocessing", "processing_status", "updated_at"))
                result = OCRResult.objects.create(
                    job=job,
                    page=page,
                    plain_text=page_output.text,
                    mean_confidence=page_output.confidence,
                    raw_output=page_output.raw(),
                )
                page_regions = _page_regions(page_output, page)
                all_regions.extend(page_regions)
                for sequence, region in enumerate(page_output.regions):
                    OCRRegion.objects.create(
                        result=result,
                        sequence=sequence,
                        text=region.text,
                        confidence=region.confidence,
                        bounding_box=region.bounding_box,
                    )
                if page_output.confidence is not None:
                    confidence_values.append(page_output.confidence)

                if document.document_type == UploadedDocument.Type.RESPONSE:
                    classify_page(page, page_output.text)

            expected_page_numbers = set(document.pages.values_list("page_number", flat=True))
            missing_output_pages = sorted(expected_page_numbers - processed_page_numbers)
            if missing_output_pages:
                raise RuntimeError(
                    "OCR returned no result for source page(s): "
                    + ", ".join(str(number) for number in missing_output_pages)
                )

            confidence = sum(confidence_values) / len(confidence_values) if confidence_values else None
            if document.document_type == UploadedDocument.Type.TEMPLATE:
                version = document.questionnaire.versions.first()
                if not version:
                    version = QuestionnaireVersion.objects.create(
                        questionnaire=document.questionnaire,
                        version_number=1,
                        expected_page_count=document.page_count,
                    )
                version.expected_page_count = document.page_count
                for result in job.results.select_related("page"):
                    update_template_page(version, result.page.page_number, result.plain_text)
                detected = detect_schema(all_regions)
                persisted = persist_detected_schema(version, detected)
                structured = {
                    "detected_questions": detected,
                    "persisted_count": persisted,
                    "expected_page_count": document.page_count,
                }
                if not detected:
                    warnings.append("No questions were detected; add or correct the questionnaire schema manually.")
                version.parse_status = QuestionnaireVersion.ParseStatus.NEEDS_REVIEW
                version.parser_version = PARSER_VERSION
                version.raw_schema = structured
                version.save(
                    update_fields=(
                        "parse_status",
                        "parser_version",
                        "raw_schema",
                        "expected_page_count",
                        "updated_at",
                    )
                )
            else:
                structured = {
                    "response_id": str(response_id),
                    "processed_page_count": len(output.pages),
                    "aggregation": "pending_other_pages",
                }

            ExtractionResult.objects.update_or_create(
                job=job,
                defaults={
                    "parser_version": PARSER_VERSION,
                    "confidence": confidence,
                    "structured_output": structured,
                    "warnings": warnings,
                },
            )

        job.engine = output.engine
        job.model_version = output.model_version
        job.status = OCRJob.Status.NEEDS_REVIEW
        document.status = UploadedDocument.Status.NEEDS_REVIEW
        succeeded = True
    except Exception as exc:
        job.status = OCRJob.Status.FAILED
        job.error_code = exc.__class__.__name__[:80]
        job.error_message = str(exc)[:4000]
        document.status = UploadedDocument.Status.FAILED
        document.failure_reason = "Document processing failed. Review the job error or retry."
        document.pages.update(processing_status=DocumentPage.ProcessingStatus.FAILED)
        Notification.objects.create(
            user=document.owner,
            kind=Notification.Kind.OCR_FAILED,
            title="Questionnaire processing failed",
            message=f"We could not process {document.original_filename}.",
            data={"document_id": str(document.id), "response_id": str(response_id) if response_id else None},
        )
        raise
    finally:
        job.finished_at = timezone.now()
        job.processing_ms = int((time.monotonic() - started) * 1000)
        job.save(
            update_fields=(
                "status",
                "engine",
                "model_version",
                "finished_at",
                "processing_ms",
                "error_code",
                "error_message",
                "updated_at",
            )
        )
        document.save(update_fields=("status", "failure_reason", "updated_at"))
        if response_id:
            refresh_response_validation(response_id)
            response, aggregated = aggregate_response_answers(response_id)
            update_batch_status(response.batch_id)
            if succeeded and aggregated:
                Notification.objects.create(
                    user=document.owner,
                    kind=Notification.Kind.REVIEW_REQUIRED,
                    title="Respondent response ready for review",
                    message=f"{response.respondent_reference} has finished page processing.",
                    data={"document_id": str(document.id), "response_id": str(response.id)},
                )
        elif succeeded:
            Notification.objects.create(
                user=document.owner,
                kind=Notification.Kind.REVIEW_REQUIRED,
                title="Questionnaire template ready for review",
                message=f"{document.original_filename} has finished processing.",
                data={"document_id": str(document.id), **structured},
            )
        if document.order_id:
            from apps.orders.services import document_finished
            document_finished(document)
    return str(document.id)
