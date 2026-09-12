from celery import shared_task
from django.db import transaction

from .generator import generate_payloads
from .models import BotRun, SyntheticResponse


@shared_task(bind=True, autoretry_for=(), max_retries=0)
def generate_synthetic_responses(self, run_id):
    run = BotRun.objects.select_related("questionnaire_version").get(pk=run_id)
    run.status = BotRun.Status.PROCESSING
    run.error_message = ""
    run.save(update_fields=("status", "error_message", "updated_at"))
    try:
        payloads = generate_payloads(run.questionnaire_version, run.requested_responses, run.seed)
        with transaction.atomic():
            run.responses.all().delete()
            SyntheticResponse.objects.bulk_create(
                [SyntheticResponse(run=run, sequence=index, answers=answers) for index, answers in enumerate(payloads, 1)]
            )
            run.generated_responses = len(payloads)
            run.status = BotRun.Status.COMPLETED
            run.save(update_fields=("generated_responses", "status", "updated_at"))
    except Exception as exc:
        run.status = BotRun.Status.FAILED
        run.error_message = str(exc)[:4000]
        run.save(update_fields=("status", "error_message", "updated_at"))
        raise

