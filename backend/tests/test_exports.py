import csv
from io import StringIO

import pytest
from django.utils import timezone

from apps.questionnaires.models import (
    Answer,
    Question,
    Questionnaire,
    QuestionnaireVersion,
    Response,
    ResponseBatch,
)


@pytest.mark.django_db
def test_csv_export_has_one_response_per_row(client, user):
    questionnaire = Questionnaire.objects.create(owner=user, title="Study")
    version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)
    q1 = Question.objects.create(version=version, key="q1", position=1, text="Department", type="SHORT_TEXT")
    q2 = Question.objects.create(version=version, key="q2", position=2, text="Interests", type="MULTIPLE_CHOICE")
    from apps.questionnaires.models import QuestionOption
    for i, label in enumerate(["AI", "Databases"], 1):
        QuestionOption.objects.create(question=q2, key=str(i), position=i, label=label)
    batch = ResponseBatch.objects.create(owner=user, questionnaire_version=version, name="August Batch")
    response = Response.objects.create(batch=batch, respondent_reference="R-001", status="CONFIRMED", confirmed_at=timezone.now())
    Answer.objects.create(response=response, question=q1, value_text="Computer Science", confidence=.98)
    Answer.objects.create(response=response, question=q2, value_json=["AI", "Databases"], confidence=.93)

    from tests.test_response_grouping import completed_page
    completed_page(user, response, 1, "Department", "Computer Science")
    Answer.objects.all().update(review_status="APPROVED", provenance="APPROVED")
    exported = client.get(f"/api/v1/exports/batches/{batch.id}/csv/")
    assert exported.status_code == 200
    rows = list(csv.reader(StringIO(exported.content.decode("utf-8-sig"))))
    assert rows[0] == ["response_id", "respondent_reference", "status", "Department", "Interests"]
    assert rows[1][1:] == ["R-001", "CONFIRMED", "Computer Science", "AI; Databases"]

