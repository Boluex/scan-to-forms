import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import BadHeaderError, EmailMessage, send_mail
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.email import ResendEmailBackend, ResendEmailError


@pytest.fixture
def resend(settings):
    # Auth throttles use a cache independent of the rolled-back test database.
    cache.clear()
    settings.EMAIL_BACKEND = "apps.core.email.ResendEmailBackend"
    settings.RESEND_API_KEY = "unit-test-key-not-a-credential"
    settings.DEFAULT_FROM_EMAIL = "ScanToForms <test@example.com>"
    settings.RESEND_TIMEOUT_SECONDS = 4
    with patch("apps.core.email.urlopen") as transport:
        response = transport.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'{"id":"test-message-id"}'
        yield transport
    cache.clear()


def test_resend_posts_account_message_over_https(resend):
    assert send_mail("Verify account", "verification link", None, ["user@example.com"]) == 1
    request = resend.call_args.args[0]
    assert request.full_url == "https://api.resend.com/emails"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer unit-test-key-not-a-credential"
    assert resend.call_args.kwargs["timeout"] == 4
    assert json.loads(request.data) == {
        "from": "ScanToForms <test@example.com>",
        "to": ["user@example.com"],
        "subject": "Verify account",
        "text": "verification link",
    }


@pytest.mark.parametrize("failure", [
    HTTPError("https://api.resend.com/emails", 403, "provider detail", {}, BytesIO(b"private data")),
    HTTPError("https://api.resend.com/emails", 429, "provider detail", {}, BytesIO(b"private data")),
    URLError("private data"),
    TimeoutError("private data"),
])
def test_resend_failures_are_not_reported_as_sent(resend, failure):
    resend.side_effect = failure
    with pytest.raises(ResendEmailError) as exc:
        send_mail("Reset", "secret-reset-token", None, ["user@example.com"])
    assert "private data" not in str(exc.value)
    assert "secret-reset-token" not in str(exc.value)
    assert "unit-test-key" not in str(exc.value)
    assert send_mail("Reset", "secret-reset-token", None, ["user@example.com"], fail_silently=True) == 0


@pytest.mark.parametrize("body", [b'{}', b'null', b'not-json'])
def test_resend_requires_provider_acknowledgement(resend, body):
    resend.return_value.__enter__.return_value.read.return_value = body
    with pytest.raises(ResendEmailError):
        send_mail("Verify", "link", None, ["user@example.com"])


def test_missing_key_and_header_injection_never_send(resend, settings):
    settings.RESEND_API_KEY = ""
    with pytest.raises(ImproperlyConfigured):
        send_mail("Verify", "link", None, ["user@example.com"])
    settings.RESEND_API_KEY = "unit-test-key-not-a-credential"
    with pytest.raises(BadHeaderError):
        send_mail("Hello\nBcc: other@example.com", "body", None, ["user@example.com"])
    assert ResendEmailBackend().send_messages([]) == 0
    assert EmailMessage("Empty", "body", to=[]).send() == 0
    resend.assert_not_called()


@pytest.mark.django_db
def test_registration_failure_rolls_back_account(resend):
    resend.side_effect = URLError("unavailable")
    client = APIClient()
    client.raise_request_exception = False
    response = client.post(reverse("register"), {
        "email": "new@example.com", "name": "Test", "password": "Long-Testing-Passphrase-421!",
    }, format="json")
    assert response.status_code == 500
    assert not User.objects.filter(email="new@example.com").exists()


@pytest.mark.django_db
def test_registration_and_reset_use_resend_transport(resend, settings):
    client = APIClient()
    email = "new@example.com"
    assert client.post(reverse("register"), {
        "email": email, "name": "Test", "password": "Long-Testing-Passphrase-421!",
    }, format="json").status_code == 201
    verification = json.loads(resend.call_args.args[0].data)
    token = parse_qs(urlparse(verification["text"].split("Verify your account: ")[1]).query)["token"][0]
    assert client.get(reverse("verify-email"), {"token": token}).status_code == 200
    assert client.post(reverse("password-reset"), {"email": email}, format="json").status_code == 200
    reset = json.loads(resend.call_args.args[0].data)
    assert reset["to"] == [email]
    assert reset["text"].startswith(settings.FRONTEND_URL + "/reset-password?")
    params = {k: v[0] for k, v in parse_qs(urlparse(reset["text"]).query).items()}
    assert client.post(reverse("password-reset-confirm"), {
        **params, "password": "Replacement-Testing-Passphrase-653!",
    }, format="json").status_code == 200
    assert User.objects.get(email=email).check_password("Replacement-Testing-Passphrase-653!")
