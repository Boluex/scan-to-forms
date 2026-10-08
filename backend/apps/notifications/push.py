"""A bounded, durable outbox. Delivery is at least once, never a read receipt."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from firebase_admin import messaging

from apps.core.firebase import firebase_app

from .models import PushDelivery


def send_pending(limit=100):
    sent = 0
    for _ in range(limit):
        with transaction.atomic():
            # Row lock prevents two senders from claiming the same delivery.
            row = (
                PushDelivery.objects.select_for_update(skip_locked=True)
                .filter(sent_at__isnull=True, attempts__lt=8, next_attempt_at__lte=timezone.now())
                .select_related("notification", "device", "device__user")
                .order_by("next_attempt_at")
                .first()
            )
            if not row:
                break
            device, notice = row.device, row.notification
            if (
                not device.active
                or device.user_id != notice.user_id
                or not device.user.is_active
                or device.user.account_status in ("SUSPENDED", "DEACTIVATED")
            ):
                row.attempts = 8
                row.last_error = "device_unavailable"
                row.save(update_fields=["attempts", "last_error"])
                continue
            row.attempts += 1
            try:
                # Generic lock-screen copy avoids exposing questionnaire/user data.
                messaging.send(
                    messaging.Message(
                        token=device.token,
                        data={
                            "title": "ScanToForms update",
                            "body": "You have a new update. Open your inbox to view it.",
                            "url": "/notifications",
                            "notification_id": str(notice.pk),
                        },
                        webpush=messaging.WebpushConfig(headers={"TTL": "86400"}),
                    ),
                    app=firebase_app(),
                )
                row.sent_at = timezone.now()
                row.last_error = ""
                sent += 1
            except messaging.UnregisteredError:
                device.active = False
                device.save(update_fields=["active", "updated_at"])
                row.attempts = 8
                row.last_error = "unregistered"
            except Exception as exc:
                # Keep tokens, message bodies and credential details out of logs.
                row.last_error = type(exc).__name__[:80]
                row.next_attempt_at = timezone.now() + timedelta(
                    seconds=min(3600, 30 * 2**row.attempts)
                )
            row.save(
                update_fields=["attempts", "sent_at", "last_error", "next_attempt_at", "updated_at"]
            )
    return sent
