import csv
from io import BytesIO, StringIO

import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.accounts.models import EmailVerificationToken, User
from apps.core.spreadsheets import safe_cell
from apps.documents.services.grouping import aggregate_response_answers
from apps.exports.services import render_csv, render_xlsx
from apps.googleforms.services import resolve_script_source
from apps.questionnaires.models import Response
from tests.test_googleforms import human_source
from tests.test_uploads import png_upload


@pytest.mark.django_db
def test_template_cannot_attach_to_foreign_response(client, user, other_user):
    own, _ = human_source(user)
    foreign, _ = human_source(other_user)
    result = client.post(
        "/api/v1/documents/",
        {
            "document_type": "TEMPLATE",
            "questionnaire": str(own.questionnaire_version.questionnaire_id),
            "response": str(foreign.responses.first().id),
            "upload": png_upload(),
        },
        format="multipart",
    )
    assert result.status_code == 400


@pytest.mark.django_db
def test_regroup_preserves_manual_correction_and_invalidates_confirmation(client, user):
    batch, _ = human_source(user)
    response = batch.responses.first()
    answer = response.answers.first()
    assert (
        client.patch(
            f"/api/v1/answers/{answer.id}/", {"value_text": "Human correction"}, format="json"
        ).status_code
        == 200
    )
    response.refresh_from_db()
    assert response.status == "NEEDS_REVIEW" and response.confirmed_at is None
    aggregate_response_answers(response.id, force=True)
    answer.refresh_from_db()
    assert answer.value_text == "Human correction" and answer.provenance == "MANUAL"
    assert (
        client.post(f"/api/v1/responses/{response.id}/confirm/", {}, format="json").status_code
        == 200
    )
    page = response.pages.first()
    assert (
        client.patch(
            f"/api/v1/response-pages/{page.id}/",
            {"assigned_template_page_number": 1},
            format="json",
        ).status_code
        == 200
    )
    response.refresh_from_db()
    answer.refresh_from_db()
    assert response.status != "CONFIRMED" and response.confirmed_at is None
    assert answer.value_text == "Human correction"
    assert answer.review_status == "NEEDS_REVIEW"
    with pytest.raises(Exception, match="Confirm at least one"):
        resolve_script_source(user, "RESPONSE_BATCH", batch.id)


@pytest.mark.django_db
def test_verification_does_not_reactivate_suspended_account(user):
    _, token = EmailVerificationToken.issue(user)
    user.account_status = User.AccountStatus.SUSPENDED
    user.save()
    assert APIClient().get("/api/v1/auth/verify-email/", {"token": token}).status_code == 403
    user.refresh_from_db()
    assert user.account_status == "SUSPENDED"


@pytest.mark.parametrize("value", ["=1+1", "+SUM(A1)", "-1+2", "@SUM(A1)", " \t=1", "\n@SUM(A1)"])
def test_formula_neutralization(value):
    assert safe_cell(value) == "'" + value


@pytest.mark.django_db
def test_final_exports_exclude_drafts_and_quote_formulas(user):
    batch, _ = human_source(user)
    response = batch.responses.first()
    response.answers.update(value_text="=1+1")
    Response.objects.create(batch=batch, respondent_reference="unfinished")
    payload, count = render_xlsx(batch)
    assert count == 1
    cell = load_workbook(BytesIO(payload))["Responses"]["D2"]
    assert cell.data_type == "s" and cell.value == "'=1+1"
    payload, count = render_csv(batch)
    rows = list(csv.reader(StringIO(payload.decode("utf-8-sig"))))
    assert count == 1 and rows[1][3] == "'=1+1"


@pytest.mark.django_db
def test_all_human_resource_reads_and_mutations_are_owner_scoped(client, other_user):
    batch, _ = human_source(other_user)
    response = batch.responses.first()
    page = response.pages.first()
    paths = [
        f"questionnaires/{batch.questionnaire_version.questionnaire_id}",
        f"response-batches/{batch.id}",
        f"responses/{response.id}",
        f"response-pages/{page.id}",
        f"documents/{page.document_id}",
    ]
    for path in paths:
        assert client.get(f"/api/v1/{path}/").status_code == 404
    assert (
        client.patch(
            f"/api/v1/answers/{response.answers.first().id}/",
            {"value_text": "intrusion"},
            format="json",
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/response-pages/{page.id}/",
            {"assigned_template_page_number": 1},
            format="json",
        ).status_code
        == 404
    )
    assert client.post(f"/api/v1/responses/{response.id}/confirm/").status_code == 404
    assert client.get(f"/api/v1/documents/{page.document_id}/file/").status_code == 404


@pytest.mark.parametrize(
    "url",
    [
        "https://forms.gle/abc",
        "https://docs.google.com/forms/d/e/" + "a" * 25 + "/viewform",
        "https://docs.google.com:invalid/forms/d/" + "a" * 25,
        "https://evil.example/forms/d/" + "a" * 25,
        "nonsense",
    ],
)
def test_invalid_google_forms_links_fail_explicitly(url):
    from rest_framework.exceptions import ValidationError

    from apps.googleforms.serializers import normalize_form_id

    with pytest.raises(ValidationError):
        normalize_form_id(url)


@pytest.mark.django_db
def test_bot_script_and_export_reads_are_owner_scoped(client, other_user):
    from apps.botlab.models import BotRun
    from apps.googleforms.models import AppsScriptJob
    batch, _ = human_source(other_user)
    run = BotRun.objects.create(owner=other_user, questionnaire_version=batch.questionnaire_version, requested_responses=1, seed=1)
    script = AppsScriptJob.objects.create(owner=other_user, source_type='RESPONSE_BATCH', batch=batch, questionnaire_version=batch.questionnaire_version, form_id='a'*25, mappings={}, script='private script', response_count=1, data_classification='HUMAN')
    owner_client = APIClient()
    owner_client.force_authenticate(other_user)
    paths = [f'bot-lab/runs/{run.pk}/', f'google-forms/scripts/{script.pk}/', f'google-forms/scripts/{script.pk}/download/', f'exports/batches/{batch.pk}/csv/']
    for path in paths:
        assert owner_client.get('/api/v1/' + path).status_code == 200
        assert client.get('/api/v1/' + path).status_code == 404
    assert client.post(f'/api/v1/questionnaires/{batch.questionnaire_version.questionnaire_id}/versions/', {}, format='json').status_code == 404
    assert client.delete(f'/api/v1/response-batches/{batch.pk}/').status_code == 404
    assert client.get('/api/v1/bot-lab/runs/').data['count'] == 0
    assert client.get('/api/v1/google-forms/scripts/').data['count'] == 0
