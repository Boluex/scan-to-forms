from datetime import date, time
from decimal import Decimal, InvalidOperation

from .models import Answer, Question, Response


def invalidate_response(response, *, recheck_answers=False):
    response.status = Response.Status.NEEDS_REVIEW
    response.confirmed_at = None
    response.reviewed_by = None
    response.save(update_fields=("status", "confirmed_at", "reviewed_by", "updated_at"))
    if recheck_answers:
        response.answers.update(review_status=Answer.ReviewStatus.NEEDS_REVIEW)
    # Imported lazily so the legacy questionnaire app stays independently usable.
    from django.apps import apps
    if apps.is_installed("apps.orders"):
        from apps.orders.services import invalidate_batch_delivery
        invalidate_batch_delivery(response.batch_id)


def answer_error(answer):
    q = answer.question
    value = answer.value_json if answer.value_json not in ({}, [], None) else answer.value_text
    empty = value is None or value == [] or value == {} or (isinstance(value, str) and not value.strip())
    if empty:
        return "Required answer is missing." if q.required else None
    options = {o.value or o.label for o in q.options.all()}
    if q.type in (Question.Type.SINGLE_CHOICE, Question.Type.DROPDOWN):
        if not isinstance(value, str) or value not in options:
            return "Choose one configured option."
    if q.type == Question.Type.MULTIPLE_CHOICE:
        if not isinstance(value, list) or any(not isinstance(v, str) or v not in options for v in value):
            return "Supply an array of configured options."
    if q.type in (Question.Type.NUMBER, Question.Type.LINEAR_SCALE, Question.Type.LIKERT):
        if q.type == Question.Type.LIKERT and options and str(value) in options:
            return None
        try:
            number = Decimal(str(value))
            if not number.is_finite():
                raise InvalidOperation
            if "min" in q.validation_rules and number < Decimal(str(q.validation_rules["min"])):
                return "Answer is below the minimum."
            if "max" in q.validation_rules and number > Decimal(str(q.validation_rules["max"])):
                return "Answer is above the maximum."
        except (InvalidOperation, ValueError, TypeError):
            return "Supply a valid number."
    try:
        if q.type == Question.Type.DATE:
            date.fromisoformat(str(value))
        if q.type == Question.Type.TIME:
            time.fromisoformat(str(value))
    except ValueError:
        return "Supply a valid ISO date/time."
    if q.type in (Question.Type.SINGLE_GRID, Question.Type.MULTIPLE_GRID):
        rows = q.validation_rules.get("rows", [])
        columns = q.validation_rules.get("columns", [])
        if not rows or not columns or not isinstance(value, list) or len(value) != len(rows):
            return "Grid requires configured rows/columns and one answer per row."
        for item in value:
            selections = item if q.type == Question.Type.MULTIPLE_GRID else [item]
            if not isinstance(selections, list) or any(v not in columns for v in selections):
                return "Invalid grid selection."
    return None


def final_errors(response, *, require_confirmation=True):
    errors = []
    if require_confirmation and (response.status != Response.Status.CONFIRMED or not response.confirmed_at):
        errors.append("Response is not confirmed.")
    pages = list(response.pages.all())
    if len(pages) != response.expected_page_count:
        errors.append("Physical page count is incomplete.")
    if sorted(p.assigned_template_page_number or 0 for p in pages) != list(range(1, response.expected_page_count + 1)):
        errors.append("Page assignments are incomplete or duplicated.")
    if any(p.processing_status != "COMPLETED" or p.validation_issues for p in pages):
        errors.append("Resolve page processing and classification issues.")
    if any(i.get("severity", "ERROR") == "ERROR" for i in response.validation_issues):
        errors.append("Resolve response validation issues.")
    questions = set(response.batch.questionnaire_version.questions.values_list("id", flat=True))
    answers = list(response.answers.select_related("question").prefetch_related("question__options"))
    if not questions or {a.question_id for a in answers} != questions:
        errors.append("The answer set does not match the questionnaire.")
    for answer in answers:
        if answer.review_status not in (Answer.ReviewStatus.APPROVED, Answer.ReviewStatus.CORRECTED):
            errors.append(f"Review question {answer.question.key}.")
        error = answer_error(answer)
        if error:
            errors.append(f"{answer.question.key}: {error}")
    return errors


def final_responses(batch):
    return [r for r in batch.responses.filter(status=Response.Status.CONFIRMED, confirmed_at__isnull=False)
            .select_related("batch__questionnaire_version").prefetch_related("pages", "answers__question__options")
            .order_by("sequence", "created_at") if not final_errors(r)]
