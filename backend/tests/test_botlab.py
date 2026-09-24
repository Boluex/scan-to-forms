from datetime import timedelta

import pytest
from django.utils import timezone

from apps.billing.models import Plan, Subscription
from apps.questionnaires.models import Question, Questionnaire, QuestionnaireVersion


def questionnaire_version(user):
    questionnaire = Questionnaire.objects.create(owner=user, title="Bot Test")
    version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)
    Question.objects.create(
        version=version,
        key="department",
        position=1,
        text="Department",
        type=Question.Type.SHORT_TEXT,
        required=True,
    )
    Question.objects.create(
        version=version,
        key="rating",
        position=2,
        text="Rating",
        type=Question.Type.LIKERT,
        required=True,
    )
    return version


@pytest.mark.django_db
def test_free_user_cannot_start_bot_lab(client, user):
    version = questionnaire_version(user)
    response = client.post(
        "/api/v1/bot-lab/runs/",
        {"questionnaire_version": str(version.id), "requested_responses": 5},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_student_gets_one_labeled_bot_lab_run(client, user):
    plan = Plan.objects.get(code=Plan.Code.STUDENT)
    Subscription.objects.create(
        user=user,
        plan=plan,
        billing_cycle=Subscription.BillingCycle.MONTHLY,
        status=Subscription.Status.ACTIVE,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )
    version = questionnaire_version(user)
    created = client.post(
        "/api/v1/bot-lab/runs/",
        {"questionnaire_version": str(version.id), "requested_responses": 5},
        format="json",
    )
    assert created.status_code == 201
    run_id = created.data["id"]
    detail = client.get(f"/api/v1/bot-lab/runs/{run_id}/")
    assert detail.data["status"] == "COMPLETED"
    exported = client.get(f"/api/v1/bot-lab/runs/{run_id}/csv/")
    assert exported.status_code == 200
    assert b"SYNTHETIC TEST DATA" in exported.content

    second = client.post(
        "/api/v1/bot-lab/runs/",
        {"questionnaire_version": str(version.id), "requested_responses": 5},
        format="json",
    )
    assert second.status_code == 402
