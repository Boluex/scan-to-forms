from django.core.management.base import BaseCommand

from apps.documents.cleanup import delete_pending
from apps.documents.models import StorageDeletion


class Command(BaseCommand):
    help = "Retry committed source deletions using this deployment's configured storage."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        ids = list(StorageDeletion.objects.order_by("created_at").values_list("pk", flat=True)[:max(0, options["limit"])])
        deleted = sum(delete_pending(pk) for pk in ids)
        self.stdout.write(f"Deleted: {deleted}; pending from this run: {len(ids) - deleted}")
