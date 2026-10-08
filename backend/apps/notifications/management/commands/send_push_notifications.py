import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from apps.notifications.push import send_pending


class Command(BaseCommand):
    help = "Drain the durable push outbox; run separately from OCR."

    def add_arguments(self, parser):
        parser.add_argument("--watch", action="store_true")
        parser.add_argument("--interval", type=int, default=15)
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if not settings.FIREBASE_PUSH_ENABLED or not settings.FIREBASE_PROJECT_ID:
            raise CommandError("Configure Firebase and enable FIREBASE_PUSH_ENABLED first.")
        if options["interval"] < 5 or not 1 <= options["limit"] <= 1000:
            raise CommandError("Use interval >= 5 and limit 1..1000.")
        try:
            while True:
                close_old_connections()
                sent = send_pending(options["limit"])
                self.stdout.write(f"Push deliveries accepted by Firebase: {sent}")
                if not options["watch"]:
                    break
                time.sleep(options["interval"])
        except KeyboardInterrupt:
            self.stdout.write("Push sender stopped.")
