import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import APIException

from apps.orders import services
from apps.orders.models import Order
from apps.orders.serializers import SchemaSerializer


class Command(BaseCommand):
    help = "Inspect or start an existing paid order; uses the same operator/payment gates as the website."

    def add_arguments(self, parser):
        parser.add_argument("--order", required=True, help="Order reference, e.g. STF-000001")
        parser.add_argument("--operator", required=True, help="Existing administrator email")
        parser.add_argument(
            "--action", choices=["status", "process", "synthetic"], default="status"
        )
        parser.add_argument("--schema", help="Reviewed schema JSON to install before processing")

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(email__iexact=options["operator"])
            services.operator(actor)
            if actor.account_status in {"SUSPENDED", "DEACTIVATED"}:
                raise CommandError("Operator account is unavailable.")
            order = Order.objects.get(reference=options["order"])
            if options["action"] == "status" and options["schema"]:
                raise CommandError("Status is read-only; omit --schema.")
            if options["action"] == "synthetic" and order.service_type != "SYNTHETIC_DATA":
                raise CommandError("Use --action process for human digitization orders.")
            if options["schema"]:
                serializer = SchemaSerializer(data=json.loads(Path(options["schema"]).read_text()))
                serializer.is_valid(raise_exception=True)
                services.prepare_schema(order, actor, serializer.validated_data["questions"])
            if options["action"] == "process":
                services.start_processing(order, actor)
            elif options["action"] == "synthetic":
                if order.status != "PROCESSING":
                    services.start_processing(order, actor)
                order.refresh_from_db()
                services.generate_synthetic(order, actor)
            order.refresh_from_db()
            self.stdout.write(
                json.dumps(
                    {
                        "order": order.reference,
                        "status": order.status,
                        "payment": order.payment_status,
                        "uploads": services.upload_summary(order),
                        "note": "Review and release results in the admin workspace. This command never verifies payment or marks results ready.",
                    },
                    indent=2,
                )
            )
        except (get_user_model().DoesNotExist, Order.DoesNotExist) as exc:
            raise CommandError("Order or operator not found.") from exc
        except (APIException, OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
