from rest_framework import serializers

from .models import PaymentTransaction, Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    features = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = (
            "code",
            "name",
            "description",
            "monthly_price_kobo",
            "yearly_price_kobo",
            "monthly_page_limit",
            "monthly_bot_lab_runs",
            "batch_size_limit",
            "max_team_members",
            "contact_required",
            "has_xlsx",
            "has_google_forms",
            "has_advanced_exports",
            "has_analytics",
            "priority_processing",
            "features",
        )

    def get_features(self, obj) -> list[str]:
        values = [f"{obj.monthly_page_limit} OCR pages per month"]
        if obj.batch_size_limit > 1:
            values.append(f"Batches of up to {obj.batch_size_limit} responses")
        else:
            values.append("Basic OCR and human review")
        values.append("CSV exports")
        if obj.has_xlsx:
            values.append("XLSX exports")
        if obj.has_google_forms:
            values.append("Google Forms Apps Script workflow")
        if obj.has_advanced_exports:
            values.append("Advanced exports (coming soon)")
        if obj.has_analytics:
            values.append("Advanced analytics (coming soon)")
        if obj.monthly_bot_lab_runs:
            values.append(f"{obj.monthly_bot_lab_runs} Bot Lab run(s) per month")
        if obj.max_team_members > 1:
            values.append(f"Up to {obj.max_team_members} team members (admin-managed)")
        if obj.priority_processing:
            values.append("Priority processing (coming soon)")
        return values


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = (
            "plan",
            "billing_cycle",
            "status",
            "current_period_start",
            "current_period_end",
            "cancel_at_period_end",
        )


class PaymentTransactionSerializer(serializers.ModelSerializer):
    plan_code = serializers.CharField(source="plan.code", read_only=True, allow_null=True)

    class Meta:
        model = PaymentTransaction
        fields = (
            "id",
            "product",
            "plan_code",
            "billing_cycle",
            "reference",
            "amount_kobo",
            "currency",
            "status",
            "authorization_url",
            "paid_at",
            "created_at",
        )


class CheckoutSerializer(serializers.Serializer):
    product = serializers.ChoiceField(choices=PaymentTransaction.Product.choices)
    plan_code = serializers.ChoiceField(choices=Plan.Code.choices, required=False)
    billing_cycle = serializers.ChoiceField(choices=Subscription.BillingCycle.choices, required=False)

    def validate(self, attrs):
        if attrs["product"] == PaymentTransaction.Product.SUBSCRIPTION:
            if not attrs.get("plan_code") or not attrs.get("billing_cycle"):
                raise serializers.ValidationError("Choose a plan and billing cycle.")
            if attrs["plan_code"] == Plan.Code.FREE:
                raise serializers.ValidationError("The Free plan does not require payment.")
        return attrs


class VerifyPaymentSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)


class PaystackWebhookSerializer(serializers.Serializer):
    event = serializers.CharField(max_length=80)
    data = serializers.JSONField(required=False)
