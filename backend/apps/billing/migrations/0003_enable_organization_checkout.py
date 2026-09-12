from django.db import migrations


def enable_checkout(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Plan.objects.filter(code="ORGANIZATION").update(contact_required=False)


class Migration(migrations.Migration):
    dependencies = [("billing", "0002_seed_plans")]

    operations = [migrations.RunPython(enable_checkout, migrations.RunPython.noop)]
