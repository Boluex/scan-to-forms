from django.contrib import admin


class InspectOnlyAdmin(admin.ModelAdmin):
    """Operational writes go through audited services, never raw model editing."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


from .models import AuditLog  # noqa: E402


@admin.register(AuditLog)
class AuditLogAdmin(InspectOnlyAdmin):
    list_display = ('action', 'actor', 'target_type', 'target_id', 'created_at')
    search_fields = ('action', 'actor__email', 'target_id')
    list_filter = ('action', 'created_at')
    readonly_fields = tuple(field.name for field in AuditLog._meta.fields)
