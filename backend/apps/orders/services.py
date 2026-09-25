import secrets
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.models import record_audit
from apps.notifications.models import Notification
from apps.questionnaires.integrity import final_errors
from apps.questionnaires.models import (
    Answer,
    Question,
    Questionnaire,
    QuestionnaireVersion,
    QuestionOption,
    Response,
    ResponseBatch,
)

from .models import Order, OrderEvent

TRANSITIONS = {
    "DRAFT": {"UPLOADING", "CANCELLED"},
    "UPLOADING": {"AWAITING_PAYMENT", "CANCELLED"},
    "AWAITING_PAYMENT": {"UPLOADING", "PAYMENT_SUBMITTED", "CANCELLED"},
    "PAYMENT_SUBMITTED": {"PAID", "AWAITING_PAYMENT"},
    "PAID": {"QUEUED", "PROCESSING", "NEEDS_REVIEW"},
    "QUEUED": {"PROCESSING", "FAILED", "NEEDS_REVIEW"},
    "PROCESSING": {"NEEDS_REVIEW", "FAILED", "READY"},
    "NEEDS_REVIEW": {"QUEUED", "PROCESSING", "READY", "FAILED"},
    "READY": {"COMPLETED", "NEEDS_REVIEW"},
    "COMPLETED": {"NEEDS_REVIEW"},
    "FAILED": {"QUEUED", "PROCESSING", "NEEDS_REVIEW"},
    "CANCELLED": set(),
}


def operator(actor):
    if not actor or not actor.is_active or not actor.is_staff:
        raise PermissionDenied("An authorized operator is required.")


def log_event(order, actor, action, *, before="", note="", metadata=None):
    OrderEvent.objects.create(
        order=order,
        actor=actor,
        action=action,
        from_status=before,
        to_status=order.status,
        note=note,
        metadata=metadata or {},
    )
    record_audit(
        actor=actor,
        action=f"order.{action}",
        target=order,
        metadata={"reference": order.reference, **(metadata or {})},
    )


def notify(order, kind, title, message=""):
    Notification.objects.create(
        user=order.user,
        kind=kind,
        title=title,
        message=message,
        data={"order_reference": order.reference},
    )


def transition(order, target, actor, *, note=""):
    if target not in TRANSITIONS.get(order.status, set()):
        raise ValidationError(f"Cannot transition {order.status} to {target}.")
    if (
        target in {"PAID", "QUEUED", "PROCESSING", "READY", "COMPLETED"}
        and order.payment_status != "VERIFIED"
    ):
        raise ValidationError("Verified payment is required.")
    before = order.status
    order.status = target
    order.save()
    log_event(order, actor, "status_changed", before=before, note=note)


def price_for(service, count):
    field = (
        "DIGITIZATION_PRICE_PER_RESPONDENT_NGN"
        if service == "DIGITIZATION"
        else "SYNTHETIC_PRICE_PER_RESPONSE_NGN"
    )
    try:
        rate = Decimal(getattr(settings, field))
        if not rate.is_finite() or rate <= 0:
            raise InvalidOperation
        amount = (rate * count).quantize(Decimal("0.01"))
        if amount > Decimal("9999999999.99"):
            raise InvalidOperation
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError("Pricing has not been configured. Please contact support.") from exc
    return amount, {
        "model": "per_response",
        "currency": "NGN",
        "unit_rate": str(rate),
        "quantity": count,
    }


def bank_details():
    return {
        "bank_name": settings.BANK_NAME,
        "account_name": settings.BANK_ACCOUNT_NAME,
        "account_number": settings.BANK_ACCOUNT_NUMBER,
    }


def payment_available():
    return settings.MANUAL_BANK_TRANSFER_ENABLED and all(bank_details().values())


@transaction.atomic
def create_order(user, data):
    questions = data.pop("questions", [])
    service = data["service_type"]
    count = (
        data["respondent_count"] if service == "DIGITIZATION" else data["synthetic_response_count"]
    )
    amount, snapshot = price_for(service, count)
    questionnaire = Questionnaire.objects.create(owner=user, title=data["title"])
    pages = (
        data["pages_per_respondent"] if service == "DIGITIZATION" else data["expected_page_count"]
    )
    version = QuestionnaireVersion.objects.create(
        questionnaire=questionnaire, version_number=1, expected_page_count=pages
    )
    for i, text in enumerate(questions, 1):
        Question.objects.create(
            version=version, key=f"q{i}", position=i, text=text, type="SHORT_TEXT"
        )
    batch = None
    if service == "DIGITIZATION":
        data["expected_page_count"] = count * pages
        batch = ResponseBatch.objects.create(
            owner=user, questionnaire_version=version, name=data["title"]
        )
        Response.objects.bulk_create(
            [
                Response(
                    batch=batch,
                    sequence=i,
                    respondent_reference=f"R-{i:04d}",
                    expected_page_count=pages,
                )
                for i in range(1, count + 1)
            ]
        )
    order = Order.objects.create(
        user=user,
        questionnaire=questionnaire,
        response_batch=batch,
        amount_ngn=amount,
        pricing_snapshot=snapshot,
        **data,
    )
    order.reference = f"STF-{order.pk:06d}"
    order.save(update_fields=["reference"])
    log_event(
        order,
        user,
        "created",
        metadata={
            "classification": "SYNTHETIC TEST DATA"
            if service == "SYNTHETIC_DATA"
            else "DIGITIZED HUMAN RESPONSES"
        },
    )
    transition(order, "UPLOADING", user)
    return order


def upload_summary(order):
    documents = list(order.uploads.all())
    responses = [d for d in documents if d.document_type == "RESPONSE"]
    templates = [d for d in documents if d.document_type == "TEMPLATE"]
    relevant = responses if order.service_type == "DIGITIZATION" else templates
    uploaded = sum(d.page_count for d in relevant)
    hashes = [d.sha256 for d in relevant]
    duplicate = len(set(hashes)) != len(hashes)
    complete = uploaded == order.expected_page_count and not duplicate
    missing = []
    if order.response_batch_id:
        for response in order.response_batch.responses.prefetch_related("pages").all():
            numbers = [p.assigned_template_page_number for p in response.pages.all()]
            if sorted(n or 0 for n in numbers) != list(range(1, order.pages_per_respondent + 1)):
                missing.append(response.sequence)
        complete = complete and not missing
    return {
        "expected_pages": order.expected_page_count,
        "uploaded_pages": uploaded,
        "template_pages": sum(d.page_count for d in templates),
        "expected_respondents": order.respondent_count,
        "duplicate_files": duplicate,
        "incomplete_respondents": missing,
        "complete": complete,
    }


@transaction.atomic
def submit_for_payment(order, actor):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not payment_available():
        raise ValidationError("Bank transfer instructions are not configured yet.")
    if not upload_summary(order)["complete"]:
        raise ValidationError(
            "Upload the expected pages and resolve duplicate/missing pages before payment."
        )
    transition(order, "AWAITING_PAYMENT", actor)
    return order


@transaction.atomic
def claim_payment(order, actor, sender="", reference=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != "AWAITING_PAYMENT" or not payment_available():
        raise ValidationError("This order is not awaiting a bank transfer.")
    order.payment_status = "SUBMITTED"
    order.payment_sender_name = sender
    order.payment_reference = reference
    order.payment_claimed_at = timezone.now()
    order.payment_rejection_reason = ""
    transition(order, "PAYMENT_SUBMITTED", actor)
    log_event(order, actor, "payment_claimed", metadata={"sender_name": sender, "payment_reference": reference})
    return order


@transaction.atomic
def verify_payment(order, actor):
    operator(actor)
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != "PAYMENT_SUBMITTED" or order.payment_status != "SUBMITTED":
        raise ValidationError("Payment must be submitted before verification.")
    order.payment_status = "VERIFIED"
    order.payment_verified_at = timezone.now()
    order.payment_verified_by = actor
    transition(order, "PAID", actor)
    log_event(order, actor, "payment_verified", metadata={"amount_ngn": str(order.amount_ngn)})
    notify(order, "PAYMENT_VERIFIED", f"{order.reference}: payment verified")
    return order


@transaction.atomic
def reject_payment(order, actor, reason):
    operator(actor)
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != "PAYMENT_SUBMITTED" or not reason.strip():
        raise ValidationError("A submitted payment and rejection reason are required.")
    order.payment_status = "REJECTED"
    order.payment_rejection_reason = reason.strip()
    transition(order, "AWAITING_PAYMENT", actor, note=reason)
    log_event(order, actor, "payment_rejected", note=reason)
    notify(order, "PAYMENT_REJECTED", f"{order.reference}: payment needs attention", reason)
    return order


def require_paid(order):
    if (
        order.payment_status != "VERIFIED"
        or not order.payment_verified_at
        or order.status == "CANCELLED"
    ):
        raise PermissionDenied("Payment must be verified before processing or results.")


@transaction.atomic
def prepare_schema(order, actor, questions):
    operator(actor)
    order = Order.objects.select_for_update().get(pk=order.pk)
    require_paid(order)
    version = order.questionnaire.versions.first()
    if (
        order.status not in {"PAID", "NEEDS_REVIEW", "FAILED"}
        or version.questions.filter(answers__isnull=False).exists()
        or order.bot_run_id
    ):
        raise ValidationError(
            "Prepare the schema before processing. Existing reviewed data cannot be replaced."
        )
    if len(questions) != order.question_count:
        raise ValidationError(f"Provide exactly {order.question_count} questions.")
    version.questions.all().delete()
    for data in questions:
        options = data.pop("options", [])
        question = Question.objects.create(version=version, **data)
        for option in options:
            QuestionOption.objects.create(question=question, **option)
    version.parse_status = "VALID"
    version.save(update_fields=["parse_status", "updated_at"])
    log_event(order, actor, "schema_prepared")
    return order


@transaction.atomic
def start_processing(order, actor):
    operator(actor)
    order = Order.objects.select_for_update().get(pk=order.pk)
    require_paid(order)
    if order.status not in {"PAID", "NEEDS_REVIEW", "FAILED"}:
        raise ValidationError("Order cannot start processing in its current state.")
    if not upload_summary(order)["complete"]:
        raise ValidationError("Resolve upload completeness before processing.")
    version = order.questionnaire.versions.first()
    if version.parse_status != "VALID" or version.questions.count() != order.question_count:
        raise ValidationError("An operator must verify the complete questionnaire schema first.")
    order.processing_started_at = order.processing_started_at or timezone.now()
    if order.service_type == "SYNTHETIC_DATA":
        transition(order, "PROCESSING", actor)
    elif settings.PROCESSING_MODE == "manual":
        # No OCR result is fabricated. An operator must transcribe each page and approve its answers.
        transition(order, "PROCESSING", actor, note="Manual transcription; OCR has not run.")
        for response in order.response_batch.responses.all():
            for question in version.questions.all():
                Answer.objects.get_or_create(response=response, question=question)
        transition(
            order,
            "NEEDS_REVIEW",
            actor,
            note="Awaiting operator transcription and page inspection.",
        )
    elif settings.PROCESSING_MODE == "celery":
        from apps.documents.models import OCRJob
        from apps.documents.tasks import process_document

        jobs = []
        for document in order.uploads.filter(document_type="RESPONSE"):
            job, _ = OCRJob.objects.get_or_create(document=document)
            if job.status == "PROCESSING":
                raise ValidationError("A job is already processing.")
            if job.status in {"COMPLETED", "NEEDS_REVIEW"}:
                continue
            job.status = "QUEUED"
            job.save(update_fields=["status", "updated_at"])
            document.status = "QUEUED"
            document.save(update_fields=["status", "updated_at"])
            jobs.append(str(job.pk))
        if not jobs:
            raise ValidationError("All pages have already been processed. Resolve review issues instead of queueing again.")
        transition(order, "QUEUED", actor)
        transaction.on_commit(lambda: dispatch_jobs(order.pk, jobs, process_document))
    else:
        raise ValidationError("Processing mode is not configured.")
    notify(
        order,
        "PROCESSING_STARTED",
        f"{order.reference}: processing started",
        "We will notify you when your order is ready.",
    )
    return order


def dispatch_jobs(order_id, jobs, task):
    try:
        for job in jobs:
            task.delay(job)
    except Exception:
        # Durable jobs remain retryable; never claim that failed broker delivery succeeded.
        order = Order.objects.get(pk=order_id)
        if order.status not in {"READY", "COMPLETED"}:
            order.status = "FAILED"
            order.save(update_fields=["status", "updated_at"])
            log_event(
                order, None, "queue_failed", note="Broker delivery failed; operator may retry."
            )
            notify(order, "NEEDS_ATTENTION", f"{order.reference}: processing needs attention")


@transaction.atomic
def invalidate_batch_delivery(batch_id):
    for order in Order.objects.select_for_update().filter(
        response_batch_id=batch_id, status__in=["READY", "COMPLETED"]
    ):
        order.apps_script_job = None
        order.ready_at = None
        order.completed_at = None
        transition(
            order, "NEEDS_REVIEW", None, note="Source data changed; previous delivery invalidated."
        )
        notify(order, "NEEDS_ATTENTION", f"{order.reference}: further review required")


def readiness_errors(order):
    errors = []
    if order.payment_status != "VERIFIED":
        errors.append("Payment has not been verified.")
    if order.service_type == "DIGITIZATION":
        responses = list(order.response_batch.responses.all())
        if len(responses) != order.respondent_count:
            errors.append("Respondent count does not match the order.")
        for response in responses:
            errors.extend(f"{response.respondent_reference}: {e}" for e in final_errors(response))
        if not order.apps_script_job_id:
            errors.append("Prepare the final Apps Script for the existing Google Form.")
    else:
        if (
            not order.bot_run_id
            or order.bot_run.status != "COMPLETED"
            or order.bot_run.responses.count() != order.synthetic_response_count
        ):
            errors.append("Attach a completed synthetic dataset of the requested size.")
        elif order.bot_run.responses.exclude(data_label__startswith="SYNTHETIC").exists():
            errors.append("Every synthetic row must retain its classification.")
        if order.bot_run_id and order.bot_run.status == "COMPLETED":
            from apps.questionnaires.integrity import answer_error
            from apps.questionnaires.models import Answer

            questions = list(
                order.bot_run.questionnaire_version.questions.prefetch_related("options")
            )
            for row in order.bot_run.responses.all():
                if not isinstance(row.answers, dict) or set(row.answers) != {
                    q.key for q in questions
                }:
                    errors.append(
                        f"Synthetic row {row.sequence}: questionnaire keys are incomplete."
                    )
                    continue
                for question in questions:
                    value = row.answers[question.key]
                    answer = Answer(
                        question=question,
                        value_json=value if isinstance(value, list | dict | int | float) else {},
                        value_text=""
                        if value is None or isinstance(value, list | dict)
                        else str(value),
                    )
                    error = answer_error(answer)
                    if error:
                        errors.append(f"Synthetic row {row.sequence}, {question.key}: {error}")
        if order.apps_script_job_id:
            errors.append(
                "Synthetic Google submission is disabled until classification survives submission."
            )
    return errors


@transaction.atomic
def mark_ready(order, actor):
    operator(actor)
    order = Order.objects.select_for_update().get(pk=order.pk)
    errors = readiness_errors(order)
    if errors:
        raise ValidationError(errors[:30])
    order.ready_at = timezone.now()
    transition(order, "READY", actor)
    notify(
        order,
        "ORDER_READY",
        f"{order.reference}: your order is ready",
        "Open your order to retrieve your results.",
    )
    return order


def require_delivery(order):
    require_paid(order)
    if order.status not in {"READY", "COMPLETED"} or readiness_errors(order):
        raise PermissionDenied("Results are available only after final review and release.")


@transaction.atomic
def generate_synthetic(order, actor):
    from apps.botlab.models import BotRun

    # Existing generator, used only by an operator for this paid order.
    from apps.botlab.tasks import generate_synthetic_responses

    operator(actor)
    order = Order.objects.select_for_update().get(pk=order.pk)
    require_paid(order)
    if order.service_type != "SYNTHETIC_DATA" or order.status != "PROCESSING" or order.bot_run_id:
        raise ValidationError(
            "Start the synthetic order first; an attached run cannot be replaced here."
        )
    run = BotRun.objects.create(
        owner=order.user,
        questionnaire_version=order.questionnaire.versions.first(),
        requested_responses=order.synthetic_response_count,
        seed=secrets.randbits(63),
    )
    order.bot_run = run
    order.save(update_fields=["bot_run", "updated_at"])
    log_event(
        order,
        actor,
        "synthetic_generation_requested",
        metadata={"classification": "SYNTHETIC TEST DATA"},
    )
    transaction.on_commit(
        lambda: dispatch_synthetic(order.pk, str(run.pk), generate_synthetic_responses)
    )
    return order


def dispatch_synthetic(order_id, run_id, task):
    try:
        if settings.PROCESSING_MODE == "manual":
            task.run(run_id)  # Real deterministic generator, never mocked OCR.
        else:
            task.delay(run_id)
    except Exception:
        order = Order.objects.get(pk=order_id)
        order.status = "FAILED"
        order.save(update_fields=["status", "updated_at"])
        log_event(order, None, "synthetic_generation_failed")
        notify(
            order, "NEEDS_ATTENTION", f"{order.reference}: synthetic preparation needs attention"
        )


@transaction.atomic
def document_started(document):
    if not document.order_id:
        return
    order = Order.objects.select_for_update().get(pk=document.order_id)
    require_paid(order)
    if order.status == "QUEUED":
        transition(order, "PROCESSING", None)


@transaction.atomic
def document_finished(document):
    if not document.order_id:
        return
    order = Order.objects.select_for_update().get(pk=document.order_id)
    states = list(
        order.uploads.filter(document_type="RESPONSE").values_list("ocr_job__status", flat=True)
    )
    if (
        states
        and not any(s in (None, "QUEUED", "PROCESSING") for s in states)
        and order.status in {"PROCESSING", "QUEUED", "FAILED"}
    ):
        transition(
            order,
            "NEEDS_REVIEW",
            None,
            note="Operator review is required before any customer result is released.",
        )
        notify(order, "NEEDS_ATTENTION", f"{order.reference}: operator review in progress")
