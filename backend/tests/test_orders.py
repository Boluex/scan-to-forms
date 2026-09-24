from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.core.models import AuditLog
from apps.documents.models import OCRJob
from apps.notifications.models import Notification
from apps.orders import services
from apps.orders.models import Order, OrderEvent
from apps.orders.views import OrderUploadThrottle

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def order_environment(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = tmp_path
    settings.ENABLE_LEGACY_WORKSPACE = False
    settings.PROCESSING_MODE = 'manual'
    monkeypatch.setattr(OrderUploadThrottle, 'rate', '10000/minute', raising=False)


@pytest.fixture
def admin(user):
    from apps.accounts.models import User
    return User.objects.create_user(email='operator@example.com', name='Operator', is_staff=True, password='OperatorPassphrase42!')


@pytest.fixture
def operator_client(admin):
    client = APIClient()
    client.force_authenticate(admin)
    return client


def image_upload(index=1):
    output = BytesIO()
    Image.new('RGB', (20, 20), (index % 255, index // 255, 80)).save(output, format='PNG')
    return SimpleUploadedFile(f'page-{index}.png', output.getvalue(), content_type='image/png')


def new_order(client, service='DIGITIZATION', respondents=1, pages=1):
    data = {'title': 'Customer questionnaire', 'service_type': service, 'question_count': 1, 'questions': ['Department?'], 'google_form_url': 'https://docs.google.com/forms/d/1234567890abcdefghijklmnopqrstuvwxyz/edit'}
    if service == 'DIGITIZATION':
        data.update(respondent_count=respondents, pages_per_respondent=pages)
    else:
        data.update(synthetic_response_count=5, expected_page_count=pages)
    result = client.post('/api/v1/orders/', data, format='json')
    assert result.status_code == 201, result.data
    return Order.objects.get(reference=result.data['reference'])


def upload_all(client, order):
    for i in range(order.expected_page_count):
        data = {'upload': image_upload(i + 1), 'upload_key': f'page-{i}', 'kind': 'RESPONSE' if order.service_type == 'DIGITIZATION' else 'TEMPLATE', 'grouping_mode': 'MANUAL_RESPONSE'}
        if order.service_type == 'DIGITIZATION':
            data.update(respondent_sequence=i // order.pages_per_respondent + 1, template_page_number=i % order.pages_per_respondent + 1)
        result = client.post(f'/api/v1/orders/{order.reference}/uploads/', data, format='multipart')
        assert result.status_code == 201, result.data


def paid_order(client, operator_client, service='DIGITIZATION', pages=1):
    order = new_order(client, service, pages=pages)
    upload_all(client, order)
    root = f'/api/v1/orders/{order.reference}/'
    assert client.post(root + 'submit/').status_code == 200
    assert client.post(root + 'payment-claim/', {'sender_name': 'Customer', 'reference': 'BANK-42'}, format='json').status_code == 200
    assert operator_client.post(root + 'verify-payment/').status_code == 200
    order.refresh_from_db()
    return order


def prepare(client, order):
    result = client.post(f'/api/v1/orders/{order.reference}/schema/', {'questions': [{'key': 'q1', 'position': 1, 'text': 'Department?', 'type': 'SHORT_TEXT', 'required': True, 'template_page_number': 1, 'options': []}]}, format='json')
    assert result.status_code == 200, result.data


def test_reference_pricing_and_group_counts(client):
    order = new_order(client, respondents=2, pages=4)
    second = new_order(client, respondents=120, pages=4)
    assert order.reference == f'STF-{order.id:06d}'
    assert second.reference != order.reference
    assert order.amount_ngn == 200 and order.expected_page_count == 8
    assert order.response_batch.responses.count() == 2
    assert second.expected_page_count == 480
    assert second.response_batch.responses.count() == 120
    assert set(second.response_batch.responses.values_list('expected_page_count', flat=True)) == {4}
    upload_all(client, order)
    assert services.upload_summary(order)['complete']
    assert order.response_batch.responses.first().pages.count() == 4


def test_payment_claim_never_unlocks_and_only_admin_can_verify(client, operator_client):
    order = new_order(client)
    upload_all(client, order)
    root = f'/api/v1/orders/{order.reference}/'
    assert client.post(root + 'submit/').status_code == 200
    assert client.post(root + 'payment-claim/', {}, format='json').status_code == 200
    assert client.post(root + 'verify-payment/').status_code == 403
    assert operator_client.post(root + 'process/').status_code == 403
    assert client.get(root + 'script/').status_code == 403
    assert client.get(root + 'export/').status_code == 403
    order.refresh_from_db()
    assert order.status == 'PAYMENT_SUBMITTED' and order.payment_status == 'SUBMITTED'
    assert not OCRJob.objects.exists()
    assert operator_client.post(root + 'verify-payment/').status_code == 200
    order.refresh_from_db()
    assert order.status == 'PAID' and order.payment_verified_at and order.payment_verified_by.is_staff
    assert Notification.objects.filter(user=order.user, kind='PAYMENT_VERIFIED').exists()
    assert OrderEvent.objects.filter(order=order, action='payment_verified').count() == 1
    assert AuditLog.objects.filter(action='order.payment_verified').exists()
    assert operator_client.post(root + 'verify-payment/').status_code == 400


def test_reject_payment_requires_reason_and_allows_resubmission(client, operator_client):
    order = new_order(client)
    upload_all(client, order)
    root = f'/api/v1/orders/{order.reference}/'
    client.post(root + 'submit/')
    client.post(root + 'payment-claim/', {}, format='json')
    assert operator_client.post(root + 'reject-payment/', {'reason': ''}, format='json').status_code == 400
    assert operator_client.post(root + 'reject-payment/', {'reason': 'Transfer not found'}, format='json').status_code == 200
    order.refresh_from_db()
    assert order.status == 'AWAITING_PAYMENT' and order.payment_status == 'REJECTED'
    assert order.payment_verified_at is None
    assert Notification.objects.filter(kind='PAYMENT_REJECTED').exists()
    assert client.post(root + 'payment-claim/', {}, format='json').status_code == 200


def test_invalid_transition_and_missing_uploads(client):
    order = new_order(client, pages=4)
    with pytest.raises(ValidationError):
        services.transition(order, 'READY', order.user)
    assert client.post(f'/api/v1/orders/{order.reference}/submit/').status_code == 400
    assert services.upload_summary(order)['incomplete_respondents'] == [1]


def test_order_and_upload_ownership_and_legacy_boundary(client, other_user, operator_client):
    foreign_client = APIClient()
    foreign_client.force_authenticate(other_user)
    order = new_order(foreign_client)
    upload_all(foreign_client, order)
    root = f'/api/v1/orders/{order.reference}/'
    document = order.uploads.get()
    for suffix in ['', 'uploads/', f'uploads/{document.id}/file/', 'respondents/', 'script/', 'export/']:
        assert client.get(root + suffix).status_code == 404
    assert client.post(root + 'payment-claim/', {}, format='json').status_code == 404
    assert client.get('/api/v1/orders/').data['count'] == 0
    assert operator_client.get('/api/v1/orders/').data['count'] == 1
    for path in ['questionnaires/', 'responses/', 'documents/', 'bot-lab/runs/', 'google-forms/scripts/', 'exports/']:
        assert client.get('/api/v1/' + path).status_code == 403


def test_duplicate_upload_and_retry_idempotency(client):
    order = new_order(client, pages=2)
    root = f'/api/v1/orders/{order.reference}/uploads/'
    data = {'kind': 'RESPONSE', 'upload_key': 'slot-1', 'respondent_sequence': 1, 'template_page_number': 1}
    assert client.post(root, {**data, 'upload': image_upload()}, format='multipart').status_code == 201
    assert client.post(root, {**data, 'upload': image_upload()}, format='multipart').status_code == 201
    assert order.uploads.count() == 1
    result = client.post(root, {**data, 'upload_key': 'slot-2', 'template_page_number': 2, 'upload': image_upload()}, format='multipart')
    assert result.status_code == 400


def test_manual_paid_digitization_to_ready_script(client, operator_client):
    order = paid_order(client, operator_client)
    prepare(operator_client, order)
    root = f'/api/v1/orders/{order.reference}/'
    assert operator_client.post(root + 'process/').status_code == 200
    assert not OCRJob.objects.exists()  # Explicit human transcription, never fake OCR.
    response = order.response_batch.responses.get()
    page = response.pages.get()
    assert operator_client.post(root + 'manual-page-reviewed/', {'page_id': str(page.id)}, format='json').status_code == 200
    answer = response.answers.get()
    assert operator_client.patch(f'/api/v1/answers/{answer.id}/', {'value_text': 'Computer Science', 'review_status': 'APPROVED'}, format='json').status_code == 200
    confirmed = operator_client.post(f'/api/v1/responses/{response.id}/confirm/', {}, format='json')
    assert confirmed.status_code == 200, confirmed.data
    script = operator_client.post(root + 'prepare-script/', {'mappings': {'q1': 'Department?'}}, format='json')
    assert script.status_code == 200, script.data
    assert client.get(root + 'script/').status_code == 403
    ready = operator_client.post(root + 'ready/')
    assert ready.status_code == 200, ready.data
    assert Notification.objects.filter(kind='ORDER_READY', user=order.user).count() == 1
    delivered = client.get(root + 'script/')
    assert delivered.status_code == 200 and 'Computer Science' in delivered.data['script']
    assert 'startSubmission' in delivered.data['script']
    assert client.get(root + 'export/').status_code == 200
    # Material edits revoke delivery immediately, including an already prepared script.
    operator_client.patch(f'/api/v1/answers/{answer.id}/', {'value_text': 'Changed'}, format='json')
    order.refresh_from_db()
    assert order.status == 'NEEDS_REVIEW' and order.apps_script_job_id is None
    assert client.get(root + 'script/').status_code == 403


def test_paid_celery_order_queues_only_response_documents(client, operator_client, settings, django_capture_on_commit_callbacks):
    settings.PROCESSING_MODE = 'celery'
    order = paid_order(client, operator_client)
    prepare(operator_client, order)
    with patch('apps.documents.tasks.process_document.delay') as delay, django_capture_on_commit_callbacks(execute=True):
        result = operator_client.post(f'/api/v1/orders/{order.reference}/process/')
    assert result.status_code == 200
    assert delay.call_count == 1
    assert OCRJob.objects.count() == 1


def test_synthetic_template_is_not_respondents_and_labelled_delivery(client, operator_client, django_capture_on_commit_callbacks):
    order = paid_order(client, operator_client, service='SYNTHETIC_DATA', pages=5)
    assert order.response_batch_id is None and order.respondent_count == 0
    assert order.uploads.count() == 5 and order.synthetic_response_count == 5
    prepare(operator_client, order)
    root = f'/api/v1/orders/{order.reference}/'
    assert operator_client.post(root + 'process/').status_code == 200
    with django_capture_on_commit_callbacks(execute=True):
        result = operator_client.post(root + 'generate-synthetic/')
    assert result.status_code == 200, result.data
    order.refresh_from_db()
    assert order.bot_run.responses.count() == 5
    assert operator_client.post(root + 'attach-bot-run/', {'bot_run': str(order.bot_run_id)}, format='json').status_code == 200
    assert operator_client.post(root + 'prepare-script/', {'mappings': {}}, format='json').status_code == 400
    assert client.get(root + 'export/').status_code == 403
    assert operator_client.post(root + 'ready/').status_code == 200
    export = client.get(root + 'export/')
    assert export.status_code == 200 and b'SYNTHETIC TEST DATA' in export.content
    assert client.get(root + 'script/').status_code == 400


def test_notification_ownership(client, user, other_user):
    own = Notification.objects.create(user=user, kind='ORDER_READY', title='Own')
    other = Notification.objects.create(user=other_user, kind='ORDER_READY', title='Other')
    assert client.get('/api/v1/notifications/unread-count/').data['count'] == 1
    assert client.post(f'/api/v1/notifications/{other.pk}/mark-read/').status_code == 404
    assert client.post(f'/api/v1/notifications/{own.pk}/mark-read/').status_code == 200
    assert client.get('/api/v1/notifications/unread-count/').data['count'] == 0
