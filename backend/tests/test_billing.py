import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.billing.exceptions import PlanLimitExceeded
from apps.billing.models import Organization, PaymentTransaction, Plan, Subscription, UsageRecord
from apps.billing.services import activate_subscription, reserve_pages
from apps.questionnaires.models import Questionnaire, QuestionnaireVersion, ResponseBatch


@pytest.mark.django_db
def test_plan_catalogue_matches_launch_pricing(client):
    response = client.get(reverse("billing-plans"))
    assert response.status_code == 200
    plans = {plan["code"]: plan for plan in response.data}
    assert plans["FREE"]["monthly_page_limit"] == 10
    assert plans["STUDENT"]["monthly_price_kobo"] == 350_000
    assert plans["STUDENT"]["yearly_price_kobo"] == 3_500_000
    assert plans["STUDENT"]["monthly_bot_lab_runs"] == 1
    assert plans["RESEARCHER"]["monthly_price_kobo"] == 500_000
    assert plans["RESEARCHER"]["yearly_price_kobo"] == 5_000_000
    assert plans["RESEARCHER"]["monthly_bot_lab_runs"] == 2
    assert plans["ORGANIZATION"]["monthly_price_kobo"] == 1_500_000
    assert plans["ORGANIZATION"]["max_team_members"] == 10


@pytest.mark.django_db
def test_free_page_allowance_is_enforced(user):
    reserve_pages(user, 9)
    reserve_pages(user, 1)
    with pytest.raises(PlanLimitExceeded):
        reserve_pages(user, 1)


@pytest.mark.django_db
def test_xlsx_requires_paid_plan(client, user):
    questionnaire = Questionnaire.objects.create(owner=user, title="Study")
    version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version_number=1)
    batch = ResponseBatch.objects.create(owner=user, questionnaire_version=version, name="Batch")
    assert client.get(f"/api/v1/exports/batches/{batch.id}/xlsx/").status_code == 403

    activate_subscription(user, Plan.objects.get(code=Plan.Code.STUDENT), Subscription.BillingCycle.MONTHLY)
    assert client.get(f"/api/v1/exports/batches/{batch.id}/xlsx/").status_code == 200


@pytest.mark.django_db
def test_organization_activation_creates_workspace(user):
    plan = Plan.objects.get(code=Plan.Code.ORGANIZATION)
    activate_subscription(user, plan, Subscription.BillingCycle.MONTHLY)
    organization = Organization.objects.get(owner=user)
    assert organization.name == f"{user.name}'s organization"
    assert plan.max_team_members == 10


@pytest.mark.django_db
def test_checkout_amount_is_selected_on_server(client, settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_example"
    initialized = {
        "authorization_url": "https://checkout.paystack.com/example",
        "access_code": "access-example",
        "reference": "ignored-by-server",
    }
    with patch("apps.billing.views.PaystackClient.initialize_transaction", return_value=initialized) as initialize:
        response = client.post(
            reverse("billing-checkout"),
            {"product": "SUBSCRIPTION", "plan_code": "STUDENT", "billing_cycle": "MONTHLY"},
            format="json",
        )
    assert response.status_code == 201
    assert response.data["amount_kobo"] == 350_000
    assert initialize.call_args.args[0]["amount"] == "350000"


@pytest.mark.django_db
def test_verify_rejects_wrong_amount_without_activating(client, user, settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_example"
    plan = Plan.objects.get(code=Plan.Code.STUDENT)
    payment = PaymentTransaction.objects.create(
        user=user,
        plan=plan,
        product=PaymentTransaction.Product.SUBSCRIPTION,
        billing_cycle=Subscription.BillingCycle.MONTHLY,
        reference="STF-test-wrong-amount",
        amount_kobo=plan.monthly_price_kobo,
    )
    gateway_data = {
        "id": 1,
        "status": "success",
        "amount": 100,
        "currency": "NGN",
        "paid_at": timezone.now().isoformat(),
        "customer": {"customer_code": "CUS_test"},
    }
    with patch("apps.billing.views.PaystackClient.verify_transaction", return_value=gateway_data):
        response = client.post(reverse("billing-verify"), {"reference": payment.reference}, format="json")
    assert response.status_code == 400
    assert not Subscription.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_signed_webhook_adds_pages_once(client, user, settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_webhook"
    payment = PaymentTransaction.objects.create(
        user=user,
        product=PaymentTransaction.Product.EXTRA_PAGES,
        reference="STF-extra-pages",
        amount_kobo=150_000,
    )
    event = {
        "event": "charge.success",
        "data": {
            "id": 22,
            "reference": payment.reference,
            "status": "success",
            "amount": 150_000,
            "currency": "NGN",
            "paid_at": timezone.now().isoformat(),
            "customer": {"customer_code": "CUS_test", "email": user.email},
        },
    }
    raw = json.dumps(event, separators=(",", ":")).encode()
    signature = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw, hashlib.sha512).hexdigest()
    for _ in range(2):
        response = client.post(
            reverse("paystack-webhook"),
            data=raw,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )
        assert response.status_code == 200
    usage = UsageRecord.objects.get(account=user)
    assert usage.extra_pages == 100
