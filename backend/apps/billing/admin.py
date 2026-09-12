from django.contrib import admin

from .models import (
    Organization,
    OrganizationMembership,
    PaymentTransaction,
    Plan,
    Subscription,
    UsageRecord,
)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "monthly_price_kobo", "monthly_page_limit", "monthly_bot_lab_runs", "is_public")
    list_filter = ("is_public", "contact_required")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "billing_cycle", "status", "current_period_end")
    list_filter = ("plan", "billing_cycle", "status")
    search_fields = ("user__email", "paystack_subscription_code")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "product", "amount_kobo", "status", "paid_at")
    list_filter = ("product", "status", "currency")
    search_fields = ("reference", "user__email", "paystack_id")
    readonly_fields = ("gateway_response",)


admin.site.register(UsageRecord)
admin.site.register(Organization)
admin.site.register(OrganizationMembership)

