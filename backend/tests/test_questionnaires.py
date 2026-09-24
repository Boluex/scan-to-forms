import pytest

from apps.questionnaires.models import (
    Answer,
    Question,
    Questionnaire,
    QuestionnaireVersion,
    Response,
    ResponseBatch,
)


@pytest.mark.django_db
def test_questionnaires_are_owner_scoped(client, user, other_user):
    own = Questionnaire.objects.create(owner=user, title="Mine")
    Questionnaire.objects.create(owner=other_user, title="Private")
    response = client.get("/api/v1/questionnaires/")
    assert response.status_code == 200
    assert [item["id"] for item in response.data["results"]] == [str(own.id)]


@pytest.mark.django_db
def test_cannot_create_batch_for_another_users_version(client, other_user):
    questionnaire = Questionnaire.objects.create(owner=other_user, title="Private")
    version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)
    response = client.post(
        "/api/v1/response-batches/", {"questionnaire_version": str(version.id), "name": "Stolen"}, format="json"
    )
    assert response.status_code == 400
    assert ResponseBatch.objects.count() == 0


@pytest.mark.django_db
def test_low_confidence_answers_block_confirmation(client, user):
    questionnaire = Questionnaire.objects.create(owner=user, title="Study")
    version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)
    question = Question.objects.create(version=version, key="q1", position=1, text="Department?", type="SHORT_TEXT")
    batch = ResponseBatch.objects.create(owner=user, questionnaire_version=version, name="Batch")
    item = Response.objects.create(batch=batch, status=Response.Status.NEEDS_REVIEW)
    answer = Answer.objects.create(response=item, question=question, value_text="CS", confidence=.4)

    from tests.test_response_grouping import completed_page
    completed_page(user, item, 1, question.text, "CS")
    blocked = client.post(f"/api/v1/responses/{item.id}/confirm/", {}, format="json")
    assert blocked.status_code == 409

    corrected = client.patch(f"/api/v1/answers/{answer.id}/", {"value_text": "Computer Science"}, format="json")
    assert corrected.status_code == 200
    confirmed = client.post(f"/api/v1/responses/{item.id}/confirm/", {}, format="json")
    assert confirmed.status_code == 200
    assert confirmed.data["status"] == "CONFIRMED"

