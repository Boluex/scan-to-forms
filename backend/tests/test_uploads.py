from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.documents.models import OCRJob, UploadedDocument
from apps.questionnaires.models import Questionnaire, QuestionnaireVersion, ResponseBatch


def png_upload(name="response.png"):
    buffer = BytesIO()
    Image.new("RGB", (120, 80), "white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@pytest.mark.django_db
def test_upload_rejects_extension_content_mismatch(client, user):
    questionnaire = Questionnaire.objects.create(owner=user, title="Study")
    version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)
    batch = ResponseBatch.objects.create(owner=user, questionnaire_version=version, name="Batch")
    fake = SimpleUploadedFile("malicious.pdf", b"not actually a pdf", content_type="application/pdf")
    response = client.post(
        "/api/v1/documents/", {"document_type": "RESPONSE", "batch": str(batch.id), "upload": fake}, format="multipart"
    )
    assert response.status_code == 400
    assert UploadedDocument.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_valid_upload_is_randomized_hashed_and_queued(client, user, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    questionnaire = Questionnaire.objects.create(owner=user, title="Study")
    version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)
    batch = ResponseBatch.objects.create(owner=user, questionnaire_version=version, name="Batch")
    with patch("apps.documents.views.process_document.delay") as delay:
        response = client.post(
            "/api/v1/documents/",
            {"document_type": "RESPONSE", "batch": str(batch.id), "upload": png_upload()},
            format="multipart",
        )
    assert response.status_code == 201
    document = UploadedDocument.objects.get()
    assert document.original_filename == "response.png"
    assert document.file.name != "response.png"
    assert len(document.sha256) == 64
    assert OCRJob.objects.filter(document=document, status="QUEUED").exists()
    delay.assert_called_once()


@pytest.mark.django_db
def test_other_user_cannot_download_document(client, other_user, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    questionnaire = Questionnaire.objects.create(owner=other_user, title="Private")
    document = UploadedDocument.objects.create(
        owner=other_user,
        questionnaire=questionnaire,
        document_type="TEMPLATE",
        file=png_upload("private.png"),
        original_filename="private.png",
        content_type="image/png",
        size_bytes=12,
        sha256="a" * 64,
    )
    response = client.get(f"/api/v1/documents/{document.id}/file/")
    assert response.status_code == 404

