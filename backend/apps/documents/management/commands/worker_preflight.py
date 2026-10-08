from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from config.celery import app


class Command(BaseCommand):
    help = (
        "Check worker connections and schema without displaying secrets or running customer work."
    )

    def handle(self, *args, **options):
        try:
            if settings.PROCESSING_MODE != "celery" or settings.CELERY_TASK_ALWAYS_EAGER:
                raise CommandError("Use PROCESSING_MODE=celery and CELERY_TASK_ALWAYS_EAGER=false.")
            if not settings.OBJECT_STORAGE_ENABLED:
                raise CommandError("Remote OCR requires shared private object storage.")
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                raise CommandError(
                    "Apply pending database migrations before starting this worker revision."
                )
            self.stdout.write("Database connection and migrations: OK")
            with app.connection_for_read() as broker:
                broker.ensure_connection(max_retries=1)
            self.stdout.write("Celery broker connection: OK")
            default_storage.connection.meta.client.head_bucket(Bucket=default_storage.bucket_name)
            self.stdout.write("Private object storage connection: OK")
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(
                f"Preflight failed ({type(exc).__name__}); inspect credentials/network privately."
            ) from None
