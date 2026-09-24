import hashlib
import math
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher

from django.db import transaction
from django.db.models import Max

from apps.billing.exceptions import PlanLimitExceeded
from apps.billing.services import entitlements_for
from apps.questionnaires.integrity import invalidate_response
from apps.questionnaires.models import Answer, Response, ResponseBatch, TemplatePage

from ..models import DocumentPage, OCRJob, UploadedDocument
from .parser import map_answers

PAGE_MARKER = re.compile(r"\bpage\s*(\d{1,3})\s*(?:of|/)\s*(\d{1,3})\b", re.IGNORECASE)


def normalize_page_text(value):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", value.lower())).strip()


def template_anchors(value, limit=10):
    anchors = []
    for line in value.splitlines():
        normalized = normalize_page_text(line)
        if len(normalized) >= 8 and normalized not in anchors:
            anchors.append(normalized)
        if len(anchors) >= limit:
            break
    return anchors


def update_template_page(version, page_number, text):
    normalized = normalize_page_text(text)
    return TemplatePage.objects.update_or_create(
        version=version,
        page_number=page_number,
        defaults={
            "reference_text": text,
            "anchors": template_anchors(text),
            "text_signature": hashlib.sha256(normalized.encode()).hexdigest() if normalized else "",
        },
    )[0]


@transaction.atomic
def create_response(batch, respondent_reference="", *, user=None):
    batch = ResponseBatch.objects.select_for_update().select_related("questionnaire_version").get(pk=batch.pk)
    if user is not None:
        ensure_batch_capacity(user, batch)
    sequence = (batch.responses.aggregate(value=Max("sequence"))["value"] or 0) + 1
    reference = respondent_reference.strip() or f"R-{sequence:04d}"
    return Response.objects.create(
        batch=batch,
        sequence=sequence,
        respondent_reference=reference,
        expected_page_count=batch.questionnaire_version.expected_page_count,
        status=Response.Status.UPLOADING,
    )


def ensure_batch_capacity(user, batch, new_response_count=1):
    plan = entitlements_for(user).plan
    existing = batch.responses.count()
    if existing + new_response_count > plan.batch_size_limit:
        remaining = max(plan.batch_size_limit - existing, 0)
        raise PlanLimitExceeded(
            f"Your {plan.name} plan allows {plan.batch_size_limit} respondent response(s) in one batch; "
            f"only {remaining} more can be added."
        )


@transaction.atomic
def prepare_bulk_groups(user, batch, file_count):
    batch = ResponseBatch.objects.select_for_update().select_related("questionnaire_version").get(pk=batch.pk)
    expected = batch.questionnaire_version.expected_page_count
    group_count = math.ceil(file_count / expected)
    ensure_batch_capacity(user, batch, group_count)
    responses = [create_response(batch) for _ in range(group_count)]
    assignments = []
    for zero_index in range(file_count):
        group_index, page_index = divmod(zero_index, expected)
        response = responses[group_index]
        assignments.append(
            {
                "upload_index": zero_index + 1,
                "response_id": str(response.id),
                "respondent_reference": response.respondent_reference,
                "original_upload_order": page_index + 1,
                "template_page_number": page_index + 1,
            }
        )
    for response in responses:
        refresh_response_validation(response.id)
    return responses, assignments


@transaction.atomic
def create_document_pages(document, template_page_number=None):
    if document.pages.exists():
        return list(document.pages.all())
    response = None
    start = 1
    if document.response_id:
        response = Response.objects.select_for_update().get(pk=document.response_id)
        start = (response.pages.aggregate(value=Max("original_upload_order"))["value"] or 0) + 1
    pages = []
    for source_page_number in range(1, document.page_count + 1):
        original_order = start + source_page_number - 1
        explicit = template_page_number if document.page_count == 1 else None
        if explicit is not None:
            assigned = explicit
        elif response:
            assigned = original_order
        else:
            assigned = source_page_number
        if document.grouping_mode == UploadedDocument.GroupingMode.MANUAL_RESPONSE and explicit is not None:
            method = DocumentPage.ClassificationMethod.MANUAL
            confidence = 1
        elif response:
            method = DocumentPage.ClassificationMethod.UPLOAD_ORDER
            confidence = 0.95 if document.page_count == response.expected_page_count else 0.55
        else:
            method = DocumentPage.ClassificationMethod.UNCLASSIFIED
            confidence = None
        pages.append(
            DocumentPage.objects.create(
                document=document,
                response=response,
                page_number=source_page_number,
                original_upload_order=original_order,
                assigned_template_page_number=assigned,
                classification_method=method,
                classification_confidence=confidence,
            )
        )
    if response:
        invalidate_response(response, recheck_answers=True)
        refresh_response_validation(response.id)
    return pages


def _template_similarity(text, template_text):
    normalized = normalize_page_text(text)
    reference = normalize_page_text(template_text)
    if not normalized or not reference:
        return 0.0
    text_tokens = set(normalized.split())
    reference_tokens = set(reference.split())
    union = text_tokens | reference_tokens
    jaccard = len(text_tokens & reference_tokens) / len(union) if union else 0
    sequence = SequenceMatcher(None, normalized, reference).ratio()
    return max(jaccard, sequence)


def classify_page(page, text):
    expected = page.response.expected_page_count if page.response_id else page.document.page_count
    marker = PAGE_MARKER.search(text)
    detected = None
    confidence = None
    method = None
    if marker:
        candidate, total = map(int, marker.groups())
        if total == expected and 1 <= candidate <= expected:
            detected = candidate
            confidence = 0.99
            method = DocumentPage.ClassificationMethod.PAGE_MARKER

    if detected is None and page.response_id:
        candidates = []
        for template_page in page.response.batch.questionnaire_version.template_pages.all():
            score = _template_similarity(text, template_page.reference_text)
            candidates.append((score, template_page.page_number))
        candidates.sort(reverse=True)
        if candidates:
            best_score, best_page = candidates[0]
            runner_up = candidates[1][0] if len(candidates) > 1 else 0
            if best_score >= 0.35 and best_score - runner_up >= 0.05:
                detected = best_page
                confidence = min(best_score, 0.98)
                method = DocumentPage.ClassificationMethod.TEXT_SIMILARITY

    if detected is not None:
        page.detected_template_page_number = detected
        if page.classification_method != DocumentPage.ClassificationMethod.MANUAL:
            page.assigned_template_page_number = detected
            page.classification_method = method
            page.classification_confidence = confidence
        page.save(
            update_fields=(
                "detected_template_page_number",
                "assigned_template_page_number",
                "classification_method",
                "classification_confidence",
                "updated_at",
            )
        )
    return page


def _issue(code, message, *, severity="ERROR", **details):
    return {"code": code, "message": message, "severity": severity, **details}


@transaction.atomic
def refresh_response_validation(response_id):
    response = Response.objects.select_for_update().select_related("batch__questionnaire_version").get(pk=response_id)
    pages = list(response.pages.select_related("document").order_by("original_upload_order", "page_number"))
    expected = response.expected_page_count
    assigned = [page.assigned_template_page_number for page in pages if page.assigned_template_page_number]
    counts = Counter(assigned)
    missing = [number for number in range(1, expected + 1) if counts[number] == 0]
    duplicates = sorted(number for number, count in counts.items() if count > 1)
    response_issues = []
    if missing:
        response_issues.append(
            _issue("MISSING_PAGES", f"Missing questionnaire page(s): {', '.join(map(str, missing))}.", pages=missing)
        )
    if duplicates:
        response_issues.append(
            _issue("DUPLICATE_PAGES", f"Duplicate questionnaire page assignment(s): {', '.join(map(str, duplicates))}.", pages=duplicates)
        )
    if len(pages) > expected:
        response_issues.append(
            _issue("EXTRA_PAGES", f"Expected {expected} page(s), but {len(pages)} were uploaded.", expected=expected, actual=len(pages))
        )

    hashes = defaultdict(list)
    for page in pages:
        hashes[page.document.sha256].append(page)
    duplicate_hashes = {digest for digest, items in hashes.items() if digest and len({item.document_id for item in items}) > 1}
    if duplicate_hashes:
        response_issues.append(
            _issue("DUPLICATE_FILE", "The same uploaded image appears more than once in this response.")
        )

    logical_order = [number for number in assigned if 1 <= number <= expected]
    if len(logical_order) == expected and len(set(logical_order)) == expected and logical_order != sorted(logical_order):
        response_issues.append(
            _issue(
                "OUT_OF_ORDER",
                "Pages arrived out of order and are displayed in detected questionnaire order.",
                severity="WARNING",
            )
        )

    for page in pages:
        issues = []
        assigned_number = page.assigned_template_page_number
        if assigned_number is None:
            issues.append(_issue("UNCLASSIFIED_PAGE", "This page has no questionnaire page assignment."))
        elif not 1 <= assigned_number <= expected:
            issues.append(
                _issue(
                    "PAGE_OUT_OF_RANGE",
                    f"Page {assigned_number} is outside the expected range 1–{expected}.",
                )
            )
        if assigned_number in duplicates:
            issues.append(_issue("DUPLICATE_PAGE", f"Questionnaire page {assigned_number} appears more than once."))
        if page.document.sha256 in duplicate_hashes:
            issues.append(_issue("DUPLICATE_FILE", "This image is an exact duplicate of another upload."))
        if (
            page.classification_method != DocumentPage.ClassificationMethod.MANUAL
            and page.detected_template_page_number
            and assigned_number
            and page.detected_template_page_number != assigned_number
        ):
            issues.append(
                _issue(
                    "PAGE_MISMATCH",
                    f"Detected page {page.detected_template_page_number}, but assigned page {assigned_number}.",
                )
            )
        confidence = float(page.classification_confidence) if page.classification_confidence is not None else 0
        if page.classification_method != DocumentPage.ClassificationMethod.MANUAL and confidence < 0.65:
            issues.append(
                _issue(
                    "LOW_PAGE_CONFIDENCE",
                    "Page assignment is provisional; verify it manually.",
                    severity="WARNING",
                )
            )
        page.validation_issues = issues
        page.save(update_fields=("validation_issues", "updated_at"))

    if any(page.processing_status == DocumentPage.ProcessingStatus.FAILED for page in pages):
        response_issues.append(_issue("PAGE_OCR_FAILED", "OCR failed for at least one response page."))

    page_issue_codes = {issue["code"] for page in pages for issue in page.validation_issues}
    response.validation_issues = response_issues
    if "PAGE_OCR_FAILED" in {issue["code"] for issue in response_issues}:
        status = Response.Status.FAILED
    elif duplicates or "DUPLICATE_FILE" in page_issue_codes:
        status = Response.Status.NEEDS_REVIEW
    elif missing or "UNCLASSIFIED_PAGE" in page_issue_codes or "PAGE_OUT_OF_RANGE" in page_issue_codes:
        status = Response.Status.INCOMPLETE
    elif response_issues or page_issue_codes:
        status = Response.Status.NEEDS_REVIEW
    elif any(page.processing_status == DocumentPage.ProcessingStatus.PROCESSING for page in pages):
        status = Response.Status.PROCESSING
    elif pages and all(page.processing_status == DocumentPage.ProcessingStatus.COMPLETED for page in pages):
        status = Response.Status.NEEDS_REVIEW
    elif len(pages) == expected:
        status = Response.Status.READY_FOR_PROCESSING
    else:
        status = Response.Status.UPLOADING
    blocking = any(i.get("severity", "ERROR") == "ERROR" for i in response_issues) or any(p.validation_issues or p.processing_status != "COMPLETED" for p in pages)
    if response.status != Response.Status.CONFIRMED or blocking:
        response.status = status
        response.confirmed_at = None
        response.reviewed_by = None
    response.save(update_fields=("status", "confirmed_at", "reviewed_by", "validation_issues", "updated_at"))
    return response


def _response_regions(response):
    regions = []
    pages = response.pages.select_related("document__ocr_job").order_by(
        "assigned_template_page_number", "original_upload_order", "page_number"
    )
    for page in pages:
        result = page.ocr_results.filter(job=page.document.ocr_job).prefetch_related("regions").first()
        if not result:
            continue
        for region in result.regions.all():
            bounding_box = {
                **region.bounding_box,
                "response_page_id": str(page.id),
                "document_id": str(page.document_id),
                "template_page_number": page.assigned_template_page_number,
            }
            regions.append(
                {
                    "text": region.text,
                    "confidence": float(region.confidence) if region.confidence is not None else None,
                    "bounding_box": bounding_box,
                    "template_page_number": page.assigned_template_page_number,
                }
            )
    return regions


@transaction.atomic
def aggregate_response_answers(response_id, *, force=False):
    response = (
        Response.objects.select_for_update()
        .select_related("batch__questionnaire_version")
        .prefetch_related("answers")
        .get(pk=response_id)
    )
    statuses = list(response.documents.values_list("ocr_job__status", flat=True))
    if not statuses:
        if force:
            response.answers.filter(provenance=Answer.Provenance.OCR).exclude(review_status__in=(Answer.ReviewStatus.CORRECTED, Answer.ReviewStatus.APPROVED)).delete()
            invalidate_response(response, recheck_answers=True)
        response = refresh_response_validation(response.id)
        return response, False
    if any(status in (None, OCRJob.Status.QUEUED, OCRJob.Status.PROCESSING) for status in statuses):
        response = refresh_response_validation(response.id)
        return response, False
    if any(status == OCRJob.Status.FAILED for status in statuses):
        response.pages.filter(document__ocr_job__status=OCRJob.Status.FAILED).update(
            processing_status=DocumentPage.ProcessingStatus.FAILED
        )
        response = refresh_response_validation(response.id)
        return response, False
    if response.answers.exists() and response.status in (
        Response.Status.NEEDS_REVIEW,
        Response.Status.INCOMPLETE,
        Response.Status.CONFIRMED,
    ) and not force:
        return response, False

    regions = _response_regions(response)
    questions = response.batch.questionnaire_version.questions.all()
    mappings = map_answers(questions, regions)
    existing = {answer.question_id: answer for answer in response.answers.all()}
    for mapping in mappings:
        previous = existing.get(mapping["question"].id)
        if previous and (previous.provenance != Answer.Provenance.OCR or previous.review_status in (Answer.ReviewStatus.CORRECTED, Answer.ReviewStatus.APPROVED)):
            continue
        Answer.objects.update_or_create(response=response, question=mapping["question"], defaults={k: v for k, v in mapping.items() if k != "question"})
    invalidate_response(response)

    response = refresh_response_validation(response.id)
    return response, True


def update_batch_status(batch_id):
    batch = ResponseBatch.objects.get(pk=batch_id)
    statuses = set(batch.responses.values_list("status", flat=True))
    if not statuses:
        status = ResponseBatch.Status.DRAFT
    elif statuses == {Response.Status.CONFIRMED}:
        status = ResponseBatch.Status.COMPLETED
    elif Response.Status.FAILED in statuses and len(statuses) == 1:
        status = ResponseBatch.Status.FAILED
    elif statuses & {Response.Status.NEEDS_REVIEW, Response.Status.INCOMPLETE, Response.Status.FAILED}:
        status = ResponseBatch.Status.NEEDS_REVIEW
    else:
        status = ResponseBatch.Status.PROCESSING
    if batch.status != status:
        batch.status = status
        batch.save(update_fields=("status", "updated_at"))
    return batch
