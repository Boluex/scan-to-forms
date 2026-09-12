from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import EmailVerificationToken, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "name", "role", "account_status", "is_staff", "date_joined")
    list_filter = ("role", "account_status", "is_staff", "is_active")
    search_fields = ("email", "name", "institution")
    fieldsets = UserAdmin.fieldsets + (
        ("ScanToForms", {"fields": ("name", "institution", "role", "account_status", "email_verified_at")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + ((None, {"fields": ("email", "name", "role")}),)


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used_at")
    readonly_fields = ("user", "token_hash", "created_at", "expires_at", "used_at")

