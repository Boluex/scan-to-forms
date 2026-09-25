from django.contrib import admin

from apps.core.admin import InspectOnlyAdmin

from .models import BotRun, SyntheticResponse


@admin.register(BotRun)
class BotRunAdmin(InspectOnlyAdmin):
    list_display = ("id", "owner", "questionnaire_version", "requested_responses", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("owner__email", "questionnaire_version__questionnaire__title")


@admin.register(SyntheticResponse)
class SyntheticResponseAdmin(InspectOnlyAdmin):
    list_display = ("id", "run", "sequence", "data_label")
    readonly_fields = ("answers", "data_label")

