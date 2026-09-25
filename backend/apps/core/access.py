from django.conf import settings
from rest_framework.permissions import BasePermission


def owned(queryset, user, field="owner"):
    """Staff access is explicit; normal users are always tenant scoped."""
    return queryset if user.is_staff else queryset.filter(**{field: user})


def can_access(user, owner_id):
    return user.is_staff or user.pk == owner_id


class WorkspacePermission(BasePermission):
    message = "Use the orders workspace. This tool is available to operators only."

    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and (request.user.is_staff or getattr(settings, "ENABLE_LEGACY_WORKSPACE", False))
        )
