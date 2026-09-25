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


@pytest.mark.django_db
def test_logout_blacklists_only_own_refresh(client, user, other_user):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    foreign = str(RefreshToken.for_user(other_user))
    assert client.post(reverse('logout'), {'refresh': foreign}, format='json').status_code == 403
    own = str(RefreshToken.for_user(user))
    assert client.post(reverse('logout'), {'refresh': own}, format='json').status_code == 204
    assert APIClient().post(reverse('token-refresh'), {'refresh': own}, format='json').status_code == 401
    assert APIClient().post(reverse('token-refresh'), {'refresh': foreign}, format='json').status_code == 200


@pytest.mark.django_db
def test_password_reset_link_and_old_token_revocation(user):
    from urllib.parse import parse_qs, urlparse

    from rest_framework.test import APIClient
    anonymous = APIClient()
    login = anonymous.post(reverse('login'), {'email': user.email, 'password': 'StrongPassphrase42!'}, format='json')
    assert anonymous.post(reverse('password-reset'), {'email': user.email}, format='json').status_code == 200
    link = mail.outbox[-1].body
    assert '/reset-password?' in link
    params = {k: v[0] for k, v in parse_qs(urlparse(link).query).items()}
    result = anonymous.post(reverse('password-reset-confirm'), {**params, 'password': 'Replacement-Passphrase-44821!'}, format='json')
    assert result.status_code == 200
    anonymous.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    assert anonymous.get(reverse('me')).status_code == 401
