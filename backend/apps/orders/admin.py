from django.contrib import admin, messages
from django.utils.html import format_html
from rest_framework.exceptions import APIException

from . import services
from .models import Order, OrderEvent


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "title",
        "user",
        "service_type",
        "status",
        "payment_status",
        "amount_ngn",
        "created_at",
    )
    list_filter = ("service_type", "status", "payment_status")
    search_fields = ("reference", "title", "user__email", "payment_reference")
    readonly_fields = tuple(f.name for f in Order._meta.fields) + ("workspace_link",)
    actions = ("verify", "reject", "process", "ready", "complete")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Operator workspace")
    def workspace_link(self, obj):
        from django.conf import settings

        return format_html(
            '<a href="{}/orders/{}">Open order, payment rejection, notes and review</a>',
            settings.FRONTEND_URL,
            obj.reference,
        )

    def apply(self, request, queryset, action):
        for order in queryset:
            try:
                action(order, request.user)
                self.message_user(request, f"{order.reference}: action recorded.", messages.SUCCESS)
            except APIException as exc:
                self.message_user(request, f"{order.reference}: {exc.detail}", messages.ERROR)

    @admin.action(description="VERIFY PAYMENT (check the bank statement first)")
    def verify(self, request, queryset):
        self.apply(request, queryset, services.verify_payment)

    @admin.action(description="REJECT PAYMENT — open the order workspace to enter a reason")
    def reject(self, request, queryset):
        self.message_user(
            request,
            "Open the order workspace and choose Reject payment; a reason is mandatory.",
            messages.WARNING,
        )

    @admin.action(description="Start paid order processing")
    def process(self, request, queryset):
        self.apply(request, queryset, services.start_processing)

    @admin.action(description="Release reviewed results (READY)")
    def ready(self, request, queryset):
        self.apply(request, queryset, services.mark_ready)

    @admin.action(description="Mark delivery completed")
    def complete(self, request, queryset):
        from django.db import transaction
        from django.utils import timezone

        def finish(order, actor):
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=order.pk)
                services.require_delivery(order)
                order.completed_at = timezone.now()
                services.transition(order, "COMPLETED", actor)

        self.apply(request, queryset, finish)


@admin.register(OrderEvent)
class OrderEventAdmin(admin.ModelAdmin):
    list_display = ("order", "action", "actor", "from_status", "to_status", "created_at")
    readonly_fields = tuple(f.name for f in OrderEvent._meta.fields)
    list_filter = ("action",)
    search_fields = ("order__reference",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
