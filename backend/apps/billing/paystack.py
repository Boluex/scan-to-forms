import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings

from .exceptions import PaystackError


class PaystackClient:
    def __init__(self):
        self.base_url = settings.PAYSTACK_BASE_URL.rstrip("/")
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.timeout = settings.PAYSTACK_TIMEOUT_SECONDS

    def _request(self, method, path, payload=None):
        if not self.secret_key:
            raise PaystackError("Paystack is not configured. Add PAYSTACK_SECRET_KEY on the server.")
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Authorization": f"Bearer {self.secret_key}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode())
        except HTTPError as exc:
            try:
                result = json.loads(exc.read().decode())
                message = result.get("message") or "Paystack rejected the request."
            except (ValueError, AttributeError):
                message = "Paystack rejected the request."
            raise PaystackError(message) from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise PaystackError("Paystack is temporarily unavailable. Please try again.") from exc
        if not result.get("status"):
            raise PaystackError(result.get("message") or "Paystack could not complete the request.")
        return result["data"]

    def initialize_transaction(self, payload):
        return self._request("POST", "/transaction/initialize", payload)

    def verify_transaction(self, reference):
        return self._request("GET", f"/transaction/verify/{quote(reference, safe='')}")

    def subscription_manage_link(self, subscription_code):
        return self._request("GET", f"/subscription/{quote(subscription_code, safe='')}/manage/link")


def configured_plan_code(plan_code, billing_cycle):
    return settings.PAYSTACK_PLAN_CODES.get((plan_code, billing_cycle), "")


def plan_for_paystack_code(paystack_code):
    for key, value in settings.PAYSTACK_PLAN_CODES.items():
        if value and value == paystack_code:
            return key
    return None

