from django.contrib import admin

from .models import ExportJob


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ("batch", "owner", "format", "status", "response_count", "created_at")
    list_filter = ("format", "status", "created_at")
    readonly_fields = ("owner", "batch", "format", "status", "response_count", "error_message", "completed_at")

