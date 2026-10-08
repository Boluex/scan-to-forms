from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.notifications.models import Notification, PushDelivery, PushDevice
from apps.notifications.push import send_pending

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolate_throttle_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def google_claims(**kwargs):
    return {
        "uid": "google-123",
        "email": "google@example.com",
        "email_verified": True,
        "name": "Google Student",
        "firebase": {"sign_in_provider": "google.com"},
        **kwargs,
    }


def test_google_login_verifies_identity_without_email(settings):
    settings.FIREBASE_PROJECT_ID = "test-project"
    with (
        patch("apps.accounts.google.firebase_app"),
        patch("apps.accounts.google.auth.verify_id_token", return_value=google_claims()) as verify,
    ):
        response = APIClient().post("/api/v1/auth/google/", {"id_token": "verified-by-sdk"})
    assert response.status_code == 200
    assert response.data["access"]
    assert verify.call_args.kwargs["check_revoked"] is True
    user = User.objects.get(firebase_uid="google-123")
    assert user.account_status == "ACTIVE" and not user.has_usable_password()
    assert not user.is_staff


@pytest.mark.parametrize(
    "claims",
    [google_claims(email_verified=False), google_claims(firebase={"sign_in_provider": "password"})],
)
def test_google_rejects_wrong_provider_and_unverified_email(settings, claims):
    settings.FIREBASE_PROJECT_ID = "test-project"
    with (
        patch("apps.accounts.google.firebase_app"),
        patch("apps.accounts.google.auth.verify_id_token", return_value=claims),
    ):
        assert APIClient().post("/api/v1/auth/google/", {"id_token": "bad"}).status_code == 401
    assert not User.objects.filter(firebase_uid="google-123").exists()


def test_google_does_not_silently_link_existing_account(settings, user, client):
    settings.FIREBASE_PROJECT_ID = "test-project"
    with (
        patch("apps.accounts.google.firebase_app"),
        patch(
            "apps.accounts.google.auth.verify_id_token",
            return_value=google_claims(email=user.email),
        ),
    ):
        assert APIClient().post("/api/v1/auth/google/", {"id_token": "valid"}).status_code == 409
        assert client.post("/api/v1/auth/google/link/", {"id_token": "valid"}).status_code == 200
        assert APIClient().post("/api/v1/auth/google/", {"id_token": "valid"}).status_code == 200
        user.refresh_from_db()
        user.account_status = "SUSPENDED"
        user.save()
        assert APIClient().post("/api/v1/auth/google/", {"id_token": "valid"}).status_code == 403


def test_invalid_google_signature_fails_closed(settings):
    settings.FIREBASE_PROJECT_ID = "test-project"
    with (
        patch("apps.accounts.google.firebase_app"),
        patch("apps.accounts.google.auth.verify_id_token", side_effect=ValueError("invalid")),
    ):
        assert APIClient().post("/api/v1/auth/google/", {"id_token": "forged"}).status_code == 401


def test_only_admin_can_manage_users_and_broadcast(client, user):
    assert client.get("/api/v1/operations/users/").status_code == 403
    assert (
        client.post(
            "/api/v1/operations/announcements/", {"title": "No", "message": "No"}
        ).status_code
        == 403
    )
    user.is_staff = True
    user.save()
    assert client.get("/api/v1/operations/users/").status_code == 403


def admin_client():
    admin = User.objects.create_superuser(email="admin@example.com", name="Admin", password="pass")
    client = APIClient()
    client.force_authenticate(admin)
    return client, admin


def test_admin_control_protects_self_and_revokes_active_sessions(user):
    client, admin = admin_client()
    token = str(RefreshToken.for_user(user).access_token)
    assert (
        client.post(
            f"/api/v1/operations/users/{admin.pk}/control/", {"action": "suspend"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/operations/users/{user.pk}/control/", {"action": "suspend"}
        ).status_code
        == 200
    )
    authenticated = APIClient()
    authenticated.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert authenticated.get("/api/v1/auth/me/").status_code == 401
    assert (
        client.post(
            f"/api/v1/operations/users/{user.pk}/control/", {"action": "grant_operator"}
        ).status_code
        == 200
    )
    user.refresh_from_db()
    assert user.is_staff and user.role != "ADMIN"


def test_announcement_creates_inbox_and_push_only_for_active_users(settings, user, other_user):
    settings.FIREBASE_PUSH_ENABLED = True
    PushDevice.objects.create(user=user, token="token-a")
    other_user.is_active = False
    other_user.save()
    client, admin = admin_client()
    response = client.post(
        "/api/v1/operations/announcements/", {"title": "Maintenance", "message": "Tomorrow"}
    )
    assert response.status_code == 201 and response.data["recipients"] == 2
    assert Notification.objects.filter(user=user).count() == 1
    assert not Notification.objects.filter(user=other_user).exists()
    assert PushDelivery.objects.count() == 1


def test_push_device_ownership_and_reassignment(settings, client, user, other_user):
    settings.FIREBASE_PUSH_ENABLED = True
    token = "private-device-token-1234567890"
    assert client.post("/api/v1/notifications/devices/", {"token": token}).status_code == 200
    Notice = Notification.objects.create(user=user, kind="ORDER_READY", title="Ready")
    stranger = APIClient()
    stranger.force_authenticate(other_user)
    assert (
        stranger.delete(
            "/api/v1/notifications/devices/", {"token": token}, format="json"
        ).status_code
        == 204
    )
    assert PushDevice.objects.get(token=token).active
    assert stranger.post("/api/v1/notifications/devices/", {"token": token}).status_code == 200
    with patch("apps.notifications.push.messaging.send") as send:
        assert send_pending() == 0
        send.assert_not_called()
    assert PushDelivery.objects.get(notification=Notice).last_error == "device_unavailable"


def test_push_retries_and_does_not_repeat_success(settings, user):
    settings.FIREBASE_PUSH_ENABLED = True
    PushDevice.objects.create(user=user, token="token-a")
    Notification.objects.create(user=user, kind="ORDER_READY", title="Private order title")
    with (
        patch("apps.notifications.push.firebase_app"),
        patch(
            "apps.notifications.push.messaging.send",
            side_effect=RuntimeError("private token detail"),
        ),
    ):
        assert send_pending() == 0
    row = PushDelivery.objects.get()
    assert row.attempts == 1 and row.last_error == "RuntimeError"
    assert row.next_attempt_at > timezone.now()
    row.next_attempt_at = timezone.now()
    row.save()
    with (
        patch("apps.notifications.push.firebase_app"),
        patch("apps.notifications.push.messaging.send") as send,
    ):
        assert send_pending() == 1
        assert send.call_args.args[0].data["title"] == "ScanToForms update"
        assert send_pending() == 0
        assert send.call_count == 1


def test_expired_push_device_is_disabled(settings, user):
    from firebase_admin.messaging import UnregisteredError

    settings.FIREBASE_PUSH_ENABLED = True
    device = PushDevice.objects.create(user=user, token="expired")
    Notification.objects.create(user=user, kind="SYSTEM", title="Hello")
    with (
        patch("apps.notifications.push.firebase_app"),
        patch("apps.notifications.push.messaging.send", side_effect=UnregisteredError("expired")),
    ):
        assert send_pending() == 0
    device.refresh_from_db()
    assert not device.active
