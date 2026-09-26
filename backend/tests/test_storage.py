import json
import os
import shutil
import stat
from contextlib import contextmanager
from io import BytesIO, StringIO
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage
from django.core.management import call_command
from django.db import transaction
from PIL import Image, ImageDraw, ImageFont
from rest_framework.test import APIClient

from apps.documents import cleanup
from apps.documents.models import OCRJob, StorageDeletion, UploadedDocument, secure_upload_path
from apps.documents.storage import materialize_source_file
from apps.documents.tasks import process_document
from apps.questionnaires.models import Questionnaire
from tests.test_orders import new_order, upload_all


class PathlessStorage(Storage):
    def __init__(self):
        self.objects = {}

    def _save(self, name, content):
        self.objects[name] = b"".join(content.chunks())
        return name

    def _open(self, name, mode="rb"):
        return ContentFile(self.objects[name], name=name)

    def exists(self, name):
        return name in self.objects

    def size(self, name):
        return len(self.objects[name])

    def delete(self, name):
        self.objects.pop(name, None)

    def path(self, name):
        raise AssertionError("Remote storage has no local path")

    def url(self, name):
        raise AssertionError("Private source previews must not request public URLs")


@pytest.fixture
def source_storage(monkeypatch):
    storage = PathlessStorage()
    monkeypatch.setattr(UploadedDocument._meta.get_field("file"), "storage", storage)
    monkeypatch.setattr(cleanup, "default_storage", storage)
    return storage


def source_document(user, data=b"source", filename="source.png", content_type="image/png"):
    questionnaire = Questionnaire.objects.create(owner=user, title="Private test template")
    return UploadedDocument.objects.create(
        owner=user, questionnaire=questionnaire, document_type="TEMPLATE",
        file=ContentFile(data, name=filename), original_filename=filename,
        content_type=content_type, size_bytes=len(data), sha256="a" * 64,
    )


@pytest.mark.django_db(transaction=True)
def test_private_pathless_order_upload_and_preview(client, other_user, source_storage):
    order = new_order(client)
    upload_all(client, order)
    document = order.uploads.get()
    assert source_storage.exists(document.file.name)
    assert document.file.name.startswith(f"users/{order.user_id}/orders/{order.pk}/documents/{document.pk}/")
    root = f"/api/v1/orders/{order.reference}/uploads/{document.pk}/file/"
    own = client.get(root)
    assert own.status_code == 200
    assert own["Cache-Control"] == "private, no-store"
    assert b"PNG" in b"".join(own.streaming_content)[:8]
    own.close()
    foreign = APIClient()
    foreign.force_authenticate(other_user)
    assert foreign.get(root).status_code == 404
    assert foreign.get(f"/api/v1/documents/{document.pk}/file/").status_code in {403, 404}
    assert foreign.get(f"/api/v1/response-pages/{document.pages.get().pk}/").status_code in {403, 404}
    assert APIClient().get(root).status_code == 401
    assert client.get("/media/" + document.file.name).status_code == 404
    listing = client.get(f"/api/v1/orders/{order.reference}/uploads/")
    assert document.file.name not in json.dumps(listing.data)
    other_user.is_staff = True
    other_user.save()
    permitted = foreign.get(root)
    assert permitted.status_code == 200
    permitted.close()


@pytest.mark.django_db
def test_keys_discard_untrusted_names(user, source_storage):
    document = source_document(user)
    keys = [secure_upload_path(document, r"../../other\secret.JPG") for _ in range(2)]
    assert keys[0] != keys[1]
    assert all(key.endswith(".jpg") and "secret" not in key and ".." not in key for key in keys)
    assert secure_upload_path(document, "malware.php").endswith(".bin")
    assert document.original_filename == "source.png"


@pytest.mark.django_db
@pytest.mark.parametrize("local", [False, True])
def test_materialization_is_private_and_cleaned(user, source_storage, tmp_path, monkeypatch, local):
    if local:
        monkeypatch.setattr(UploadedDocument._meta.get_field("file"), "storage", FileSystemStorage(location=tmp_path))
    document = source_document(user, b"test source")
    with materialize_source_file(document) as path:
        assert path.read_bytes() == b"test source"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        directory = path.parent
    assert not path.exists() and not directory.exists()
    with pytest.raises(RuntimeError), materialize_source_file(document) as failed_path:
        raise RuntimeError("OCR failed")
    assert not failed_path.exists() and not failed_path.parent.exists()
    assert document.file.storage.exists(document.file.name)


@pytest.mark.django_db
def test_materialization_uses_bounded_reads_and_cleans_partial_copy(user, source_storage, monkeypatch):
    document = source_document(user)
    paths = []
    from apps.documents import storage as module
    original = module.tempfile.TemporaryDirectory

    @contextmanager
    def record_directory(**kwargs):
        with original(**kwargs) as directory:
            paths.append(directory)
            yield directory

    class BrokenStream(BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 1024 * 1024
            raise OSError("Object download interrupted")

    monkeypatch.setattr(module.tempfile, "TemporaryDirectory", record_directory)
    monkeypatch.setattr(module, "open_source_file", lambda _: BrokenStream())
    with pytest.raises(OSError), materialize_source_file(document):
        pytest.fail("An incomplete file must never reach OCR")
    assert paths and all(not os.path.exists(path) for path in paths)


@pytest.mark.django_db
@pytest.mark.parametrize("cascade", [False, True])
def test_deleted_and_cascaded_documents_clean_objects(user, source_storage, django_capture_on_commit_callbacks, cascade):
    document = source_document(user)
    name = document.file.name
    with django_capture_on_commit_callbacks(execute=True):
        if cascade:
            document.questionnaire.delete()
        else:
            UploadedDocument.objects.filter(pk=document.pk).delete()
        assert source_storage.exists(name)  # Never delete before commit.
    assert not source_storage.exists(name)
    assert not StorageDeletion.objects.exists()


@pytest.mark.django_db
def test_rollback_does_not_delete_source(user, source_storage, django_capture_on_commit_callbacks):
    document = source_document(user)
    pk, name = document.pk, document.file.name
    with django_capture_on_commit_callbacks(execute=True), pytest.raises(RuntimeError), transaction.atomic():
        document.delete()
        raise RuntimeError("rollback")
    assert UploadedDocument.objects.filter(pk=pk).exists()
    assert source_storage.exists(name)
    assert not StorageDeletion.objects.exists()


@pytest.mark.django_db
def test_failed_cleanup_is_durable_and_retryable(user, source_storage, django_capture_on_commit_callbacks):
    document = source_document(user)
    name = document.file.name
    with patch.object(source_storage, "delete", side_effect=OSError("offline")), django_capture_on_commit_callbacks(execute=True):
        document.delete()
    intent = StorageDeletion.objects.get()
    assert intent.attempts == 1 and intent.error_code == "OSError"
    assert source_storage.exists(name)
    output = StringIO()
    call_command("cleanup_source_files", stdout=output)
    assert not source_storage.exists(name) and not StorageDeletion.objects.exists()
    assert "Deleted: 1" in output.getvalue()


@pytest.mark.django_db
def test_cleanup_will_not_target_changed_storage_or_existing_reference(user, source_storage):
    document = source_document(user)
    intent = StorageDeletion.objects.create(name=document.file.name, storage_signature="wrong-bucket")
    assert not cleanup.delete_pending(intent.pk)
    intent.storage_signature = cleanup.storage_signature(source_storage)
    intent.save()
    assert not cleanup.delete_pending(intent.pk)
    assert source_storage.exists(document.file.name)


def printed_source(format):
    image = Image.new("RGB", (1400, 600), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
    draw.text((60, 100), "Department: Engineering", font=font, fill="black")
    stream = BytesIO()
    image.save(stream, format=format)
    return stream.getvalue()


@pytest.mark.django_db
@pytest.mark.skipif(not shutil.which("tesseract"), reason="Real Tesseract executable required")
@pytest.mark.parametrize("format,extension,content_type", [
    ("JPEG", "jpg", "image/jpeg"), ("PNG", "png", "image/png"), ("PDF", "pdf", "application/pdf"),
])
def test_real_ocr_without_storage_path(user, source_storage, settings, monkeypatch, format, extension, content_type):
    settings.OCR_ENGINE = "tesseract"
    document = source_document(user, printed_source(format), f"source.{extension}", content_type)
    job = OCRJob.objects.create(document=document)
    from apps.documents import tasks
    paths = []
    real_extract = tasks.extract_document

    def observe(path, engine):
        paths.append(path)
        return real_extract(path, engine)  # Real engine, no fabricated OCR output.

    monkeypatch.setattr(tasks, "extract_document", observe)
    process_document.run(str(job.pk))
    job.refresh_from_db()
    assert job.status == "NEEDS_REVIEW" and job.engine == "tesseract"
    assert "Engineering" in job.results.get().plain_text
    assert paths and all(not path.exists() for path in paths)
    assert source_storage.exists(document.file.name)


@pytest.mark.django_db
def test_ocr_failure_removes_temporary_file(user, source_storage, monkeypatch):
    document = source_document(user)
    job = OCRJob.objects.create(document=document)
    from apps.documents import tasks
    paths = []

    def fail(path, engine):
        paths.append(path)
        raise RuntimeError("OCR engine failure")

    monkeypatch.setattr(tasks, "extract_document", fail)
    with pytest.raises(RuntimeError):
        process_document.run(str(job.pk))
    job.refresh_from_db()
    assert job.status == "FAILED"
    assert paths and all(not path.exists() for path in paths)
