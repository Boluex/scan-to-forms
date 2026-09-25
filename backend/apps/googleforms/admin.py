from django.contrib import admin

from apps.core.admin import InspectOnlyAdmin

from .models import AppsScriptJob


@admin.register(AppsScriptJob)
class AppsScriptJobAdmin(InspectOnlyAdmin):
    list_display = ("id", "owner", "source_type", "form_id", "response_count", "created_at")
    list_filter = ("source_type", "data_classification")
    search_fields = ("owner__email", "form_id", "batch__name")
    readonly_fields = ("script", "mappings", "data_classification", "response_count")

