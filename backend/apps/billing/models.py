from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel


class Plan(TimeStampedModel):
    class Code(models.TextChoices):
        FREE = "FREE", "Free"
        STUDENT = "STUDENT", "Student Pro"
        RESEARCHER = "RESEARCHER", "Researcher Pro"
        ORGANIZATION = "ORGANIZATION", "Organization"

    code = models.CharField(max_length=24, choices=Code.choices, unique=True)
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    monthly_price_kobo = models.PositiveIntegerField(default=0)
    yearly_price_kobo = models.PositiveIntegerField(null=True, blank=True)
    monthly_page_limit = models.PositiveIntegerField()
    monthly_bot_lab_runs = models.PositiveIntegerField(default=0)
    batch_size_limit = models.PositiveIntegerField(default=1)
    max_team_members = models.PositiveSmallIntegerField(default=1)
    has_xlsx = models.BooleanField(default=False)
    has_google_forms = models.BooleanField(default=False)
    has_advanced_exports = models.BooleanField(default=False)
    has_analytics = models.BooleanField(default=False)
    priority_processing = models.BooleanField(default=False)
    contact_required = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("display_order",)

    def __str__(self):
        return self.name


class Subscription(TimeStampedModel):
    class BillingCycle(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"
        YEARLY = "YEARLY", "Yearly"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PAST_DUE = "PAST_DUE", "Past due"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    billing_cycle = models.CharField(max_length=12, choices=BillingCycle.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField(db_index=True)
    cancel_at_period_end = models.BooleanField(default=False)
    paystack_customer_code = models.CharField(max_length=80, blank=True)
    paystack_subscription_code = models.CharField(max_length=80, blank=True)
    paystack_email_token = models.CharField(max_length=160, blank=True)

    def __str__(self):
        return f"{self.user.email} — {self.plan.name}"


class UsageRecord(TimeStampedModel):
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="monthly_usage")
    month = models.DateField()
    pages_used = models.PositiveIntegerField(default=0)
    extra_pages = models.PositiveIntegerField(default=0)
    bot_lab_runs_used = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-month",)
        constraints = [models.UniqueConstraint(fields=("account", "month"), name="unique_account_usage_month")]


class Organization(TimeStampedModel):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_organization")
    name = models.CharField(max_length=180)

    def __str__(self):
        return self.name


class OrganizationMembership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        MEMBER = "MEMBER", "Member"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organization_membership")
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.MEMBER)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("organization", "user"), name="unique_organization_user"),
        ]

    def clean(self):
        if not self.is_active:
            return
        try:
            plan = self.organization.owner.subscription.plan
        except Subscription.DoesNotExist as exc:
            raise ValidationError("The organization owner needs an active Organization plan.") from exc
        active_count = self.organization.memberships.filter(is_active=True).exclude(pk=self.pk).count()
        if active_count >= plan.max_team_members - 1:
            raise ValidationError(f"This organization is limited to {plan.max_team_members} people.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PaymentTransaction(TimeStampedModel):
    class Product(models.TextChoices):
        SUBSCRIPTION = "SUBSCRIPTION", "Subscription"
        EXTRA_PAGES = "EXTRA_PAGES", "100 extra OCR pages"

    class Status(models.TextChoices):
        INITIALIZED = "INITIALIZED", "Initialized"
        SUCCESS = "SUCCESS", "Successful"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payment_transactions")
    plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    product = models.CharField(max_length=20, choices=Product.choices)
    billing_cycle = models.CharField(max_length=12, choices=Subscription.BillingCycle.choices, blank=True)
    reference = models.CharField(max_length=100, unique=True)
    amount_kobo = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.INITIALIZED, db_index=True)
    authorization_url = models.URLField(max_length=500, blank=True)
    access_code = models.CharField(max_length=120, blank=True)
    paystack_id = models.CharField(max_length=80, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)


class PaystackEvent(models.Model):
    payload_hash = models.CharField(max_length=64, unique=True)
    event_type = models.CharField(max_length=80, db_index=True)
    received_at = models.DateTimeField(auto_now_add=True)
