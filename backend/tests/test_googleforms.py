from datetime import timedelta

import pytest
from django.utils import timezone

from apps.billing.models import Plan, Subscription
from apps.botlab.models import BotRun, SyntheticResponse
from apps.questionnaires.models import (
    Answer,
    Question,
    Questionnaire,
    QuestionnaireVersion,
    Response,
    ResponseBatch,
)


def activate_student(user):
    Subscription.objects.create(
        user=user,
        plan=Plan.objects.get(code=Plan.Code.STUDENT),
        billing_cycle=Subscription.BillingCycle.MONTHLY,
        status=Subscription.Status.ACTIVE,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )


def human_source(user):
    questionnaire = Questionnaire.objects.create(owner=user, title="Student Study")
    version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)
    question = Question.objects.create(
        version=version,
        key="department",
        position=1,
        text="What is your department?",
        type=Question.Type.SHORT_TEXT,
    )
    batch = ResponseBatch.objects.create(owner=user, questionnaire_version=version, name="Reviewed batch")
    response = Response.objects.create(batch=batch, status=Response.Status.CONFIRMED, confirmed_at=timezone.now())
    Answer.objects.create(response=response, question=question, value_text="Computer Science", confidence=.98)
    from tests.test_response_grouping import completed_page
    completed_page(user, response, 1, question.text, "Computer Science")
    response.answers.update(review_status="APPROVED", provenance="APPROVED")
    return batch, version


@pytest.mark.django_db
def test_free_plan_cannot_generate_apps_script(client, user):
    batch, _ = human_source(user)
    response = client.get(
        f"/api/v1/google-forms/preview/?source_type=RESPONSE_BATCH&source_id={batch.id}"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_confirmed_batch_generates_resumable_apps_script(client, user):
    activate_student(user)
    batch, _ = human_source(user)
    preview = client.get(
        f"/api/v1/google-forms/preview/?source_type=RESPONSE_BATCH&source_id={batch.id}"
    )
    assert preview.status_code == 200
    assert preview.data["response_count"] == 1

    created = client.post(
        "/api/v1/google-forms/scripts/",
        {
            "source_type": "RESPONSE_BATCH",
            "source_id": str(batch.id),
            "form_id": "1234567890abcdefghijklmnopqrstuvwxyz",
            "mappings": {"department": "Department"},
        },
        format="json",
    )
    assert created.status_code == 201
    script = created.data["script"]
    assert "FormApp.openById" in script
    assert "form.createResponse()" in script
    assert "formResponse.withItemResponse" in script
    assert "formResponse.submit()" in script
    assert "previewMapping" in script
    assert "continueSubmission" in script
    assert "Computer Science" in script
    assert "CONFIRMED DIGITIZED HUMAN RESPONSES" in script

    downloaded = client.get(created.data["download_url"])
    assert downloaded.status_code == 200
    assert downloaded["Content-Disposition"].endswith('.gs"')


@pytest.mark.django_db
def test_bot_lab_script_keeps_synthetic_classification(client, user):
    activate_student(user)
    _, version = human_source(user)
    run = BotRun.objects.create(
        owner=user,
        questionnaire_version=version,
        requested_responses=1,
        generated_responses=1,
        seed=22,
        status=BotRun.Status.COMPLETED,
    )
    SyntheticResponse.objects.create(run=run, sequence=1, answers={"department": "Synthetic answer 1"})
    created = client.post(
        "/api/v1/google-forms/scripts/",
        {
            "source_type": "BOT_RUN",
            "source_id": str(run.id),
            "form_id": "1234567890abcdefghijklmnopqrstuvwxyz",
            "mappings": {"department": "Department"},
        },
        format="json",
    )
    assert created.status_code == 201
    assert created.data["data_classification"] == "SYNTHETIC DATA — NOT HUMAN RESEARCH RESPONSES"
    assert "SYNTHETIC DATA — NOT HUMAN RESEARCH RESPONSES" in created.data["script"]


@pytest.mark.django_db
def test_duplicate_google_item_titles_are_rejected(client, user):
    activate_student(user)
    batch, version = human_source(user)
    Question.objects.create(
        version=version,
        key="age",
        position=2,
        text="Age",
        type=Question.Type.NUMBER,
    )
    created = client.post(
        "/api/v1/google-forms/scripts/",
        {
            "source_type": "RESPONSE_BATCH",
            "source_id": str(batch.id),
            "form_id": "1234567890abcdefghijklmnopqrstuvwxyz",
            "mappings": {"department": "Same title", "age": "same title"},
        },
        format="json",
    )
    assert created.status_code == 400
