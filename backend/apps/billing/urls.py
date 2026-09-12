from django.urls import path

from .views import (
    BillingSummaryView,
    CheckoutView,
    PaymentHistoryView,
    PaystackWebhookView,
    PlanListView,
    SubscriptionManageView,
    VerifyPaymentView,
)

urlpatterns = [
    path("billing/plans/", PlanListView.as_view(), name="billing-plans"),
    path("billing/summary/", BillingSummaryView.as_view(), name="billing-summary"),
    path("billing/checkout/", CheckoutView.as_view(), name="billing-checkout"),
    path("billing/verify/", VerifyPaymentView.as_view(), name="billing-verify"),
    path("billing/payments/", PaymentHistoryView.as_view(), name="billing-payments"),
    path("billing/subscription/manage/", SubscriptionManageView.as_view(), name="subscription-manage"),
    path("billing/paystack/webhook/", PaystackWebhookView.as_view(), name="paystack-webhook"),
]

