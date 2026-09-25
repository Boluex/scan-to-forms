"""Resend HTTPS transport for Django's existing account emails."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailError(RuntimeError):
    """A send was not acknowledged; never include message content or credentials."""


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or []:
            if not message.recipients():
                continue
            if not settings.RESEND_API_KEY:
                raise ImproperlyConfigured("Set RESEND_API_KEY to use Resend email delivery.")
            # Preserve Django's header-injection validation before constructing JSON.
            message.message()
            if message.attachments:
                raise ValueError("The account email transport does not support attachments.")
            payload = {
                "from": message.from_email,
                "to": message.to,
                "subject": message.subject,
                "html" if message.content_subtype == "html" else "text": message.body,
            }
            for name in ("cc", "bcc", "reply_to"):
                if value := getattr(message, name):
                    payload[name] = value
            for alternative in getattr(message, "alternatives", []):
                if alternative.mimetype != "text/html":
                    raise ValueError("Unsupported account email alternative content type.")
                payload["html"] = alternative.content
            request = Request(
                "https://api.resend.com/emails",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": "ScanToForms/1.0",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=settings.RESEND_TIMEOUT_SECONDS) as response:
                    result = json.load(response)
                    if not 200 <= response.status < 300 or not isinstance(result, dict) or not result.get("id"):
                        raise ResendEmailError("Resend did not acknowledge the email.")
            except HTTPError as exc:
                if not self.fail_silently:
                    raise ResendEmailError(f"Resend rejected the email (HTTP {exc.code}).") from None
                continue
            except (URLError, OSError, ValueError, ResendEmailError):
                if not self.fail_silently:
                    raise ResendEmailError("Resend email delivery could not be confirmed.") from None
                continue
            sent += 1
        return sent
