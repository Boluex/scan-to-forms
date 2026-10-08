from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification, PushDelivery, PushDevice


@receiver(post_save, sender=Notification)
def queue_push(sender, instance, created, raw=False, **kwargs):
    # Durable outbox shares the business transaction. A separate sender drains it.
    if created and not raw and settings.FIREBASE_PUSH_ENABLED:
        PushDelivery.objects.bulk_create(
            [
                PushDelivery(notification=instance, device=device)
                for device in PushDevice.objects.filter(user=instance.user, active=True)
            ]
        )
