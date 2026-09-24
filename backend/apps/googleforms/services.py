from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.botlab.models import BotRun
from apps.questionnaires.integrity import final_responses
from apps.questionnaires.models import ResponseBatch

from .models import AppsScriptJob


@dataclass(frozen=True)
class ScriptSource:
    source_type: str
    source: object
    version: object
    title: str
    classification: str
    responses: list[dict]


def _answer_value(answer):
    if answer.value_json not in ({}, [], None):
        return answer.value_json
    return answer.value_text


def resolve_script_source(user, source_type, source_id):
    if source_type == AppsScriptJob.SourceType.RESPONSE_BATCH:
        try:
            batch = ResponseBatch.objects.select_related(
                "questionnaire_version__questionnaire"
            ).get(pk=source_id, owner=user)
        except (ResponseBatch.DoesNotExist, DjangoValidationError, ValueError) as exc:
            raise serializers.ValidationError("Response batch not found.") from exc
        confirmed = final_responses(batch)
        if not confirmed:
            raise serializers.ValidationError("Confirm at least one reviewed response before generating Apps Script.")
        responses = []
        for response in confirmed:
            responses.append(
                {
                    "id": str(response.id),
                    "answers": {answer.question.key: _answer_value(answer) for answer in response.answers.all()},
                }
            )
        return ScriptSource(
            source_type=source_type,
            source=batch,
            version=batch.questionnaire_version,
            title=batch.name,
            classification="CONFIRMED DIGITIZED HUMAN RESPONSES",
            responses=responses,
        )

    if source_type == AppsScriptJob.SourceType.BOT_RUN:
        try:
            run = BotRun.objects.select_related("questionnaire_version__questionnaire").get(
                pk=source_id,
                owner=user,
                status=BotRun.Status.COMPLETED,
            )
        except (BotRun.DoesNotExist, DjangoValidationError, ValueError) as exc:
            raise serializers.ValidationError("Completed Bot Lab run not found.") from exc
        responses = [
            {"id": str(response.id), "answers": response.answers}
            for response in run.responses.all().order_by("sequence")
        ]
        if not responses:
            raise serializers.ValidationError("This Bot Lab run has no generated responses.")
        return ScriptSource(
            source_type=source_type,
            source=run,
            version=run.questionnaire_version,
            title=f"{run.questionnaire_version.questionnaire.title} — synthetic run",
            classification="SYNTHETIC DATA — NOT HUMAN RESEARCH RESPONSES",
            responses=responses,
        )

    raise serializers.ValidationError("Unsupported Apps Script source type.")


def source_preview(source):
    questions = list(source.version.questions.order_by("position"))
    return {
        "title": source.title,
        "source_type": source.source_type,
        "data_classification": source.classification,
        "response_count": len(source.responses),
        "questions": [
            {
                "key": question.key,
                "text": question.text,
                "type": question.type,
                "suggested_google_item_title": question.text,
            }
            for question in questions
        ],
    }
