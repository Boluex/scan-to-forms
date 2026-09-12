from django.db import migrations


PLANS = (
    {
        "code": "FREE",
        "name": "Free",
        "description": "Core questionnaire digitization for occasional use.",
        "monthly_price_kobo": 0,
        "yearly_price_kobo": None,
        "monthly_page_limit": 10,
        "monthly_bot_lab_runs": 0,
        "batch_size_limit": 1,
        "max_team_members": 1,
        "has_xlsx": False,
        "has_google_forms": False,
        "has_advanced_exports": False,
        "has_analytics": False,
        "priority_processing": False,
        "contact_required": False,
        "display_order": 0,
    },
    {
        "code": "STUDENT",
        "name": "Student Pro",
        "description": "Batch tools and connected exports for student projects.",
        "monthly_price_kobo": 350000,
        "yearly_price_kobo": 3500000,
        "monthly_page_limit": 30,
        "monthly_bot_lab_runs": 1,
        "batch_size_limit": 30,
        "max_team_members": 1,
        "has_xlsx": True,
        "has_google_forms": True,
        "has_advanced_exports": False,
        "has_analytics": False,
        "priority_processing": False,
        "contact_required": False,
        "display_order": 1,
    },
    {
        "code": "RESEARCHER",
        "name": "Researcher Pro",
        "description": "Advanced exports, analytics and larger research workflows.",
        "monthly_price_kobo": 500000,
        "yearly_price_kobo": 5000000,
        "monthly_page_limit": 35,
        "monthly_bot_lab_runs": 2,
        "batch_size_limit": 100,
        "max_team_members": 1,
        "has_xlsx": True,
        "has_google_forms": True,
        "has_advanced_exports": True,
        "has_analytics": True,
        "priority_processing": False,
        "contact_required": False,
        "display_order": 2,
    },
    {
        "code": "ORGANIZATION",
        "name": "Organization",
        "description": "A shared workspace for up to 10 people with priority processing.",
        "monthly_price_kobo": 1500000,
        "yearly_price_kobo": 15000000,
        "monthly_page_limit": 100,
        "monthly_bot_lab_runs": 5,
        "batch_size_limit": 250,
        "max_team_members": 10,
        "has_xlsx": True,
        "has_google_forms": True,
        "has_advanced_exports": True,
        "has_analytics": True,
        "priority_processing": True,
        "contact_required": False,
        "display_order": 3,
    },
)


def seed_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for values in PLANS:
        code = values["code"]
        Plan.objects.update_or_create(code=code, defaults=values)


def remove_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Plan.objects.filter(code__in=[values["code"] for values in PLANS]).delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial")]

    operations = [migrations.RunPython(seed_plans, remove_plans)]
