# ruff: noqa: F811
# Pytest fixtures are imported for reuse and injected by name.
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.documents.models import OCRJob
from apps.notifications.models import Notification, PushDelivery, PushDevice
from apps.orders import services
from tests.test_orders import (  # noqa: F401
    admin,
    image_upload,
    new_order,
    operator_client,
    order_environment,
    upload_all,
)

pytestmark = pytest.mark.django_db


def test_70_respondents_uploaded_in_batches_are_280_pages(client):
    order = new_order(client, respondents=70, pages=4)
    root = f"/api/v1/orders/{order.reference}/"
    # Two customer upload batches, with stable global page slots.
    for start, end in [(0, 140), (140, 280)]:
        for i in range(start, end):
            result = client.post(
                root + "uploads/",
                {
                    "upload": image_upload(i + 1),
                    "upload_key": f"page-{i}",
                    "kind": "RESPONSE",
                    "grouping_mode": "BULK_ORDERED",
                    "respondent_sequence": i // 4 + 1,
                    "template_page_number": i % 4 + 1,
                },
                format="multipart",
            )
            assert result.status_code == 201, result.data
        if start == 0:
            assert client.post(root + "submit/").status_code == 400
    assert services.upload_summary(order)["complete"]
    assert order.response_batch.responses.count() == 70
    for response in order.response_batch.responses.prefetch_related("pages"):
        assert sorted(p.assigned_template_page_number for p in response.pages.all()) == [1, 2, 3, 4]
    assert order.uploads.count() == 280
    assert not OCRJob.objects.exists()  # Uploads alone cannot start unpaid work.
    assert client.post(root + "submit/").status_code == 200


def test_submission_notifies_admin_and_queues_push_once(client, admin, other_user, settings):
    settings.FIREBASE_PUSH_ENABLED = True
    PushDevice.objects.create(user=admin, token="test-admin-device")
    order = new_order(client)
    upload_all(client, order)
    root = f"/api/v1/orders/{order.reference}/"
    assert client.post(root + "submit/").status_code == 200
    assert client.post(root + "submit/").status_code == 400
    notices = Notification.objects.filter(user=admin, data__event="ORDER_SUBMITTED")
    assert notices.count() == 1
    assert PushDelivery.objects.filter(notification=notices.get()).count() == 1
    assert not Notification.objects.filter(user=other_user).exists()


def test_terminal_command_cannot_process_unpaid_or_as_customer(client, admin, user):
    order = new_order(client)
    upload_all(client, order)
    with pytest.raises(CommandError, match="[Pp]ayment"):
        call_command(
            "operate_order",
            order=order.reference,
            operator=admin.email,
            action="process",
            stdout=StringIO(),
        )
    with pytest.raises(CommandError, match="authorized operator"):
        call_command(
            "operate_order",
            order=order.reference,
            operator=user.email,
            action="process",
            stdout=StringIO(),
        )
    assert not OCRJob.objects.exists()
    output = StringIO()
    call_command("operate_order", order=order.reference, operator=admin.email, stdout=output)
    assert '"payment": "UNPAID"' in output.getvalue()
