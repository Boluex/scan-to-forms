import pytest
from django.core import mail
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_registration_hashes_password_and_sends_verification(api_client=None):
    from rest_framework.test import APIClient

    client = APIClient()
    response = client.post(
        reverse("register"),
        {"email": "student@example.com", "name": "Student", "password": "A genuinely strong passphrase 42!"},
        format="json",
    )
    assert response.status_code == 201
    user = User.objects.get(email="student@example.com")
    assert user.password != "A genuinely strong passphrase 42!"
    assert user.check_password("A genuinely strong passphrase 42!")
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_login_is_email_based(user):
    from rest_framework.test import APIClient

    response = APIClient().post(
        reverse("login"), {"email": user.email.upper(), "password": "StrongPassphrase42!"}, format="json"
    )
    assert response.status_code == 200
    assert "access" in response.data and "refresh" in response.data


@pytest.mark.django_db
def test_suspension_blocks_existing_and_new_sessions(user):
    from rest_framework.test import APIClient

    anonymous = APIClient()
    login = anonymous.post(
        reverse("login"), {"email": user.email, "password": "StrongPassphrase42!"}, format="json"
    )
    user.account_status = User.AccountStatus.SUSPENDED
    user.save(update_fields=["account_status"])

    relogin = anonymous.post(
        reverse("login"), {"email": user.email, "password": "StrongPassphrase42!"}, format="json"
    )
    assert relogin.status_code == 400

    authenticated = APIClient()
    authenticated.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    assert authenticated.get(reverse("me")).status_code == 401


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()
