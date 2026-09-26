# Imported pytest fixtures intentionally share names with injected parameters.
# ruff: noqa: F811
import ssl
import uuid
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from celery import Celery
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.utils import timezone

from apps.documents.execution import advisory_lock_id, execution_lock
from apps.documents.models import OCRJob
from apps.documents.services.ocr import DocumentOutput, PageOutput
from apps.documents.tasks import process_document
from config.connections import secure_redis_url
from tests.test_orders import (  # noqa: F401
    admin,
    new_order,
    operator_client,
    paid_order,
    prepare,
    upload_all,
)
from tests.test_storage import source_document, source_storage  # noqa: F401


@pytest.fixture(autouse=True)
def recovery_environment(settings, tmp_path):
    settings.PROCESSING_MODE = "celery"
    settings.MEDIA_ROOT = tmp_path


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["UPLOADING", "AWAITING_PAYMENT", "PAYMENT_SUBMITTED"])
def test_unpaid_recovery_and_direct_task_blocked(client, operator_client, state):
    order = new_order(client)
    upload_all(client, order)
    root = f"/api/v1/orders/{order.reference}/"
    if state != "UPLOADING":
        assert client.post(root + "submit/").status_code == 200
    if state == "PAYMENT_SUBMITTED":
        assert client.post(root + "payment-claim/", {}, format="json").status_code == 200
    job = OCRJob.objects.create(document=order.uploads.get())
    with patch("apps.documents.tasks.extract_document") as extract, patch("apps.documents.tasks.process_document.delay") as delay:
        for endpoint in ["process/", "retry-processing/"]:
            assert operator_client.post(root + endpoint).status_code == 403
        assert operator_client.post(f"/api/v1/documents/{job.document_id}/retry/").status_code == 403
        from rest_framework.exceptions import PermissionDenied
        with pytest.raises(PermissionDenied):
            process_document.run(str(job.pk))
        extract.assert_not_called()
        delay.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["QUEUED", "FAILED", "PROCESSING"])
def test_operator_republishes_eligible_durable_work(client, operator_client, settings, django_capture_on_commit_callbacks, state):
    order = paid_order(client, operator_client)
    prepare(operator_client, order)
    order.status = "PROCESSING" if state == "PROCESSING" else state
    order.save()
    job = OCRJob.objects.create(document=order.uploads.get(), status=state,
        execution_token=uuid.uuid4(), started_at=timezone.now() - timedelta(seconds=settings.OCR_STALE_AFTER_SECONDS + 1))
    root = f"/api/v1/orders/{order.reference}/retry-processing/"
    assert client.post(root).status_code == 403
    with patch("apps.documents.tasks.process_document.delay") as delay, django_capture_on_commit_callbacks(execute=True):
        result = operator_client.post(root)
        assert result.status_code == 200, result.data
        delay.assert_not_called()  # Publish after commit.
    delay.assert_called_once_with(str(job.pk))
    job.refresh_from_db()
    order.refresh_from_db()
    assert job.status == "QUEUED" and job.execution_token is None
    assert order.status == "QUEUED"
    assert order.events.filter(action="processing_retried").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["PROCESSING", "COMPLETED", "NEEDS_REVIEW"])
def test_retry_does_not_duplicate_running_or_final_work(client, operator_client, state):
    order = paid_order(client, operator_client)
    order.status = "PROCESSING"
    order.save()
    job = OCRJob.objects.create(document=order.uploads.get(), status=state, started_at=timezone.now())
    with patch("apps.documents.tasks.process_document.delay") as delay:
        result = operator_client.post(f"/api/v1/orders/{order.reference}/retry-processing/")
    assert result.status_code == 400
    delay.assert_not_called()
    job.refresh_from_db()
    assert job.status == state


@pytest.mark.django_db
def test_stale_timestamp_does_not_override_active_execution_lock(client, operator_client, settings):
    order = paid_order(client, operator_client)
    order.status = "PROCESSING"
    order.save()
    job = OCRJob.objects.create(document=order.uploads.get(), status="PROCESSING",
        started_at=timezone.now() - timedelta(seconds=settings.OCR_STALE_AFTER_SECONDS + 30))
    with execution_lock(job.pk) as acquired, patch("apps.documents.tasks.process_document.delay") as delay:
        assert acquired
        assert operator_client.post(f"/api/v1/orders/{order.reference}/retry-processing/").status_code == 400
        delay.assert_not_called()


@pytest.mark.django_db
def test_duplicate_task_and_late_worker_cannot_publish_results(user, source_storage, monkeypatch):
    document = source_document(user)
    job = OCRJob.objects.create(document=document)
    from apps.documents import tasks

    def superseded(path, engine):
        # Simulate lost DB session + operator recovery while old OCR finishes.
        assert process_document.run(str(job.pk)) is None  # Already executing.
        OCRJob.objects.filter(pk=job.pk).update(execution_token=None, status="QUEUED")
        return DocumentOutput("test", "test", [PageOutput(1, 10, 10, "late", 1, [], {})])

    monkeypatch.setattr(tasks, "extract_document", superseded)
    process_document.run(str(job.pk))
    job.refresh_from_db()
    assert job.status == "QUEUED" and job.execution_token is None
    assert not job.results.exists()
    job.status = "COMPLETED"
    job.save()
    with patch("apps.documents.tasks.extract_document") as extract:
        process_document.run(str(job.pk))
        extract.assert_not_called()


def test_tls_configuration_is_enforced_for_broker_and_backend():
    url = secure_redis_url("rediss://user:password@queue.example.invalid:6379/0", "/etc/ssl/certs/ca-certificates.crt")
    params = parse_qs(urlsplit(url).query)
    assert params["ssl_cert_reqs"] == ["required"]
    assert params["ssl_check_hostname"] == ["true"]
    app = Celery("tls-test", broker=url, backend=url)
    assert app.backend.connparams["ssl_cert_reqs"] == ssl.CERT_REQUIRED
    assert app.backend.connparams["ssl_check_hostname"] is True
    with app.connection_for_read() as connection:
        assert connection.ssl["ssl_cert_reqs"] == ssl.CERT_REQUIRED
        assert connection.ssl["ssl_check_hostname"] is True
    assert secure_redis_url("redis://localhost:6379/0") == "redis://localhost:6379/0"


@pytest.mark.parametrize("parameter", ["ssl_cert_reqs=none", "ssl_cert_reqs=optional", "ssl_check_hostname=false"])
def test_insecure_redis_tls_options_are_rejected(parameter):
    with pytest.raises(ImproperlyConfigured):
        secure_redis_url("rediss://queue.example.invalid/0?" + parameter)


@pytest.mark.django_db(transaction=True)
def test_execution_lock_is_exclusive_across_database_sessions():
    job_id = uuid.uuid4()
    if connection.vendor != "postgresql":
        # Local single-process SQLite mode still prevents nested/concurrent claims.
        with execution_lock(job_id) as first, execution_lock(job_id) as second:
            assert first and not second
        return
    import psycopg
    with psycopg.connect(**connection.get_connection_params(), autocommit=True) as other:
        other.execute("SELECT pg_advisory_lock(%s)", [advisory_lock_id(job_id)])
        with execution_lock(job_id) as acquired:
            assert not acquired
        other.execute("SELECT pg_advisory_unlock(%s)", [advisory_lock_id(job_id)])
        with execution_lock(job_id) as acquired:
            assert acquired
