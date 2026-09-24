import calendar
from dataclasses import dataclass
from datetime import date, datetime

from django.db import transaction
from django.utils import timezone

from .exceptions import FeatureNotAvailable, PlanLimitExceeded
from .models import Organization, OrganizationMembership, Plan, Subscription, UsageRecord


@dataclass(frozen=True)
class Entitlements:
    plan: Plan
    account: object
    subscription: Subscription | None


FREE_PLAN_DEFAULTS = {
    "name": "Free",
    "description": "Core questionnaire digitization for occasional use.",
    "monthly_price_kobo": 0,
    "yearly_price_kobo": None,
    "monthly_page_limit": 10,
    "monthly_bot_lab_runs": 0,
    "batch_size_limit": 1,
    "max_team_members": 1,
    "display_order": 0,
}


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def current_month() -> date:
    today = timezone.localdate()
    return today.replace(day=1)


def _valid_subscription(user):
    try:
        subscription = user.subscription
    except Subscription.DoesNotExist:
        return None
    if subscription.status in (Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE) and subscription.current_period_end > timezone.now():
        return subscription
    return None


def entitlements_for(user) -> Entitlements:
    subscription = _valid_subscription(user)
    account = user
    if subscription is None:
        try:
            membership = user.organization_membership
        except OrganizationMembership.DoesNotExist:
            membership = None
        if membership and membership.is_active:
            account = membership.organization.owner
            subscription = _valid_subscription(account)
            if not subscription or subscription.plan.code != Plan.Code.ORGANIZATION:
                subscription = None
                account = user
    plan = subscription.plan if subscription else Plan.objects.get_or_create(
        code=Plan.Code.FREE, defaults=FREE_PLAN_DEFAULTS
    )[0]
    return Entitlements(plan=plan, account=account, subscription=subscription)


def usage_for(user, *, lock=False):
    entitlements = entitlements_for(user)
    queryset = UsageRecord.objects
    if lock:
        queryset = queryset.select_for_update()
    usage, _ = queryset.get_or_create(account=entitlements.account, month=current_month())
    return entitlements, usage


@transaction.atomic
def reserve_pages(user, page_count: int):
    entitlements, usage = usage_for(user, lock=True)
    allowance = entitlements.plan.monthly_page_limit + usage.extra_pages
    if usage.pages_used + page_count > allowance:
        remaining = max(allowance - usage.pages_used, 0)
        raise PlanLimitExceeded(
            f"This upload needs {page_count} page(s), but your {entitlements.plan.name} plan has "
            f"{remaining} page(s) remaining this month. Upgrade or buy 100 extra pages."
        )
    usage.pages_used += page_count
    usage.save(update_fields=("pages_used", "updated_at"))
    return usage


@transaction.atomic
def add_extra_pages(user, page_count: int = 100):
    _, usage = usage_for(user, lock=True)
    usage.extra_pages += page_count
    usage.save(update_fields=("extra_pages", "updated_at"))
    return usage


@transaction.atomic
def reserve_bot_lab_run(user):
    entitlements, usage = usage_for(user, lock=True)
    limit = entitlements.plan.monthly_bot_lab_runs
    if usage.bot_lab_runs_used >= limit:
        raise PlanLimitExceeded(
            f"Your {entitlements.plan.name} plan includes {limit} Bot Lab run(s) per month. "
            "Contact the administrator for more."
        )
    usage.bot_lab_runs_used += 1
    usage.save(update_fields=("bot_lab_runs_used", "updated_at"))
    return usage


def require_feature(user, field: str):
    if user.is_staff:
        return entitlements_for(user)
    entitlements = entitlements_for(user)
    if not getattr(entitlements.plan, field, False):
        raise FeatureNotAvailable(f"{entitlements.plan.name} does not include this feature. Upgrade to continue.")
    return entitlements


@transaction.atomic
def activate_subscription(user, plan, billing_cycle, *, customer_code="", subscription_code="", email_token=""):
    now = timezone.now()
    try:
        current = Subscription.objects.select_for_update().get(user=user)
    except Subscription.DoesNotExist:
        current = None
    base = now
    if (
        current
        and current.status == Subscription.Status.ACTIVE
        and current.plan_id == plan.id
        and current.billing_cycle == billing_cycle
        and current.current_period_end > now
    ):
        base = current.current_period_end
    months = 12 if billing_cycle == Subscription.BillingCycle.YEARLY else 1
    defaults = {
        "plan": plan,
        "billing_cycle": billing_cycle,
        "status": Subscription.Status.ACTIVE,
        "current_period_start": now,
        "current_period_end": _add_months(base, months),
        "cancel_at_period_end": False,
    }
    if customer_code:
        defaults["paystack_customer_code"] = customer_code
    if subscription_code:
        defaults["paystack_subscription_code"] = subscription_code
    if email_token:
        defaults["paystack_email_token"] = email_token
    subscription, _ = Subscription.objects.update_or_create(user=user, defaults=defaults)
    if plan.code == Plan.Code.ORGANIZATION:
        Organization.objects.get_or_create(
            owner=user,
            defaults={"name": f"{user.name}'s organization"},
        )
    return subscription
