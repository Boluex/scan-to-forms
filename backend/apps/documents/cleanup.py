"""Post-commit storage cleanup with a database-backed retry record."""

import hashlib
import json
import logging

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import StorageDeletion, UploadedDocument

logger = logging.getLogger(__name__)


def storage_signature(storage):
    # Configuration identity, never credentials. Don't delete from a different bucket/root.
    identity = {
        "backend": f"{storage.__class__.__module__}.{storage.__class__.__name__}",
        "location": getattr(storage, "location", ""),
        "bucket": getattr(storage, "bucket_name", ""),
        "endpoint": getattr(storage, "endpoint_url", ""),
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def delete_pending(deletion_id, storage=None):
    storage = storage if storage is not None else default_storage
    with transaction.atomic():
        intent = StorageDeletion.objects.select_for_update().filter(pk=deletion_id).first()
        if not intent:
            return True
        intent.attempts += 1
        try:
            if storage_signature(storage) != intent.storage_signature:
                raise ValueError("Storage configuration differs from the deletion source.")
            # Protect a still-referenced legacy object; new uploads always use unique keys.
            if UploadedDocument.objects.filter(file=intent.name).exists():
                raise ValueError("An existing document still references this object.")
            storage.delete(intent.name)
        except Exception as exc:
            intent.error_code = type(exc).__name__[:100]
            intent.save(update_fields=["attempts", "error_code", "updated_at"])
            logger.warning("Storage cleanup pending: %s (%s)", intent.pk, intent.error_code)
            return False
        intent.delete()
        return True


@receiver(post_delete, sender=UploadedDocument)
def cleanup_deleted_source(sender, instance, using, **kwargs):
    if not instance.file.name:
        return
    storage = instance.file.storage
    intent = StorageDeletion.objects.using(using).create(
        name=instance.file.name, storage_signature=storage_signature(storage)
    )
    transaction.on_commit(lambda: delete_pending(intent.pk, storage), using=using, robust=True)
