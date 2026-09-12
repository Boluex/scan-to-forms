import shutil
from io import BytesIO

import pytest
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

from apps.documents.models import OCRJob, UploadedDocument
from apps.documents.services.ocr import extract_document
from apps.documents.tasks import process_document
from apps.questionnaires.models import Question, Questionnaire, QuestionnaireVersion, ResponseBatch

pytestmark = pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract executable is not installed")


def questionnaire_image(lines):
    image = Image.new("RGB", (1400, 650), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
    for index, line in enumerate(lines):
        draw.text((70, 70 + index * 130), line, fill="black", font=font)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_tesseract_produces_line_regions(tmp_path):
    path = tmp_path / "response.png"
    path.write_bytes(questionnaire_image(["What is your department?", "Computer Science"]))
    output = extract_document(path, preferred="tesseract")
    assert output.engine == "tesseract"
    assert len(output.pages) == 1
    assert "department" in output.pages[0].text.lower()
    assert any("Computer Science" in region.text for region in output.pages[0].regions)


@pytest.mark.django_db
def test_document_task_maps_response_and_confidence(user, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.OCR_ENGINE = "tesseract"
    questionnaire = Questionnaire.objects.create(owner=user, title="Department study")
    version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)
    question = Question.objects.create(
        version=version,
        key="q1",
        position=1,
        text="What is your department?",
        type=Question.Type.SHORT_TEXT,
    )
    batch = ResponseBatch.objects.create(owner=user, questionnaire_version=version, name="Field batch")
    document = UploadedDocument.objects.create(
        owner=user,
        batch=batch,
        document_type=UploadedDocument.Type.RESPONSE,
        original_filename="response.png",
        content_type="image/png",
        size_bytes=1,
        sha256="b" * 64,
    )
    document.file.save(
        "response.png",
        ContentFile(questionnaire_image(["What is your department?", "Computer Science"])),
    )
    job = OCRJob.objects.create(document=document)

    process_document.run(str(job.id))

    document.refresh_from_db()
    answer = document.response.answers.get(question=question)
    assert document.status == UploadedDocument.Status.NEEDS_REVIEW
    assert answer.value_text == "Computer Science"
    assert float(answer.confidence) > 0.65

