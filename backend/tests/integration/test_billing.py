"""Integration tests for persisted mock billing and subscriptions."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.adapters.billing import (
    BdAppsBillingProvider,
    BdAppsCredentials,
    OtpStartResult,
    SubscriptionResult,
    bdapps_credentials_for_plan,
    provider_name_for_plan,
)
from app.config import settings
from app.models import Subscription
from app.routers import billing as billing_router

pytestmark = pytest.mark.integration
MASKED_SUBSCRIBER = f"tel:{'a' * 96}"


@pytest.fixture(autouse=True)
def mock_billing_provider(monkeypatch):
    monkeypatch.setattr(settings, "BILLING_PROVIDER", "mock")
    monkeypatch.setattr(settings, "MOCK_OTP_CODE", "1234")
    for name in (
        "BDAPPS_PLUS_APPLICATION_ID",
        "BDAPPS_PLUS_API_KEY",
        "BDAPPS_PLUS_PASSWORD",
        "BDAPPS_PLUS_APPLICATION_HASH",
        "BDAPPS_PRO_APPLICATION_ID",
        "BDAPPS_PRO_PASSWORD",
        "BDAPPS_PRO_APPLICATION_HASH",
        "BDAPPS_APPLICATION_ID",
        "BDAPPS_API_KEY",
        "BDAPPS_PASSWORD",
        "BDAPPS_APPLICATION_HASH",
    ):
        monkeypatch.setattr(settings, name, "")
    monkeypatch.setattr(settings, "BDAPPS_PLAN_ID", "plus")


async def test_billing_requires_auth(client):
    assert (await client.get("/api/billing/plans")).status_code == 401
    assert (await client.get("/api/billing/subscription")).status_code == 401


async def test_plan_catalog_identifies_the_provisioned_bdapps_tariff(
    auth_client, monkeypatch
):
    mock_catalog = (await auth_client.get("/api/billing/plans")).json()
    assert mock_catalog["subscribable_plan_ids"] == ["plus", "pro"]
    assert {
        plan["id"]: plan["provider"] for plan in mock_catalog["results"]
    } == {"free": "internal", "plus": "mock", "pro": "mock"}

    monkeypatch.setattr(settings, "BILLING_PROVIDER", "bdapps")
    monkeypatch.setattr(settings, "BDAPPS_PLUS_APPLICATION_ID", "APP_PLUS")
    monkeypatch.setattr(settings, "BDAPPS_PLUS_API_KEY", "plus-api-key")
    plus_catalog = (await auth_client.get("/api/billing/plans")).json()
    assert plus_catalog["provider"] == "bdapps"
    # Mixed mode: Plus runs on the real carrier while Pro (no credentials yet)
    # stays subscribable through the labelled dev mock (OTP 1234) rather than
    # being blocked as "credentials pending". Every paid plan is subscribable.
    assert plus_catalog["subscribable_plan_ids"] == ["plus", "pro"]
    assert {
        plan["id"]: plan["provider"] for plan in plus_catalog["results"]
    } == {"free": "internal", "plus": "bdapps", "pro": "mock"}

    # Pro remains mock-only even if stale credentials exist in an environment.
    monkeypatch.setattr(settings, "BDAPPS_PRO_APPLICATION_ID", "APP_PRO")
    monkeypatch.setattr(settings, "BDAPPS_PRO_PASSWORD", "pro-secret")
    bdapps_catalog = (await auth_client.get("/api/billing/plans")).json()
    assert bdapps_catalog["provider"] == "bdapps"
    assert bdapps_catalog["subscribable_plan_ids"] == ["plus", "pro"]
    assert next(
        plan for plan in bdapps_catalog["results"] if plan["id"] == "pro"
    )["provider"] == "mock"
    assert provider_name_for_plan("pro") == "mock"


async def test_api_key_alias_and_official_otp_paths(monkeypatch):
    monkeypatch.setattr(settings, "BILLING_PROVIDER", "bdapps")
    monkeypatch.setattr(settings, "BDAPPS_PLUS_APPLICATION_ID", "APP_PLUS")
    monkeypatch.setattr(settings, "BDAPPS_PLUS_API_KEY", "issued-api-key")
    monkeypatch.setattr(settings, "BDAPPS_PLUS_PASSWORD", "old-password")

    credentials = bdapps_credentials_for_plan("plus")
    assert credentials.password == "issued-api-key"

    provider = BdAppsBillingProvider(
        BdAppsCredentials(
            plan_id="plus",
            application_id="APP_PLUS",
            password="issued-api-key",
        )
    )
    calls: list[tuple[str, dict]] = []

    async def fake_post(path: str, payload: dict) -> dict:
        calls.append((path, payload))
        if path == "/otp/request":
            return {
                "statusCode": "S1000",
                "statusDetail": "Success",
                "referenceNo": "reference-1",
            }
        return {
            "statusCode": "S1000",
            "statusDetail": "Success",
            "subscriptionStatus": "REGISTERED",
            "subscriberId": MASKED_SUBSCRIBER,
        }

    monkeypatch.setattr(provider, "_post", fake_post)
    started = await provider.request_otp("tel:8801712345678")
    verified = await provider.verify_otp(started.reference_no, "5678")

    assert [path for path, _payload in calls] == [
        "/otp/request",
        "/otp/verify",
    ]
    assert verified.ok
    assert verified.subscription_status == "REGISTERED"


async def test_bdapps_mode_without_credentials_uses_development_otp(
    auth_client, monkeypatch
):
    monkeypatch.setattr(settings, "BILLING_PROVIDER", "bdapps")

    catalog = (await auth_client.get("/api/billing/plans")).json()
    assert catalog["provider"] == "mock"
    assert catalog["subscribable_plan_ids"] == ["plus", "pro"]

    started = await auth_client.post(
        "/api/billing/otp/request", json={"plan_id": "pro"}
    )
    assert started.status_code == 201
    assert started.json()["demo_otp"] == "1234"

    verified = await auth_client.post(
        "/api/billing/otp/verify",
        json={
            "challenge_id": started.json()["challenge_id"],
            "otp": "1234",
        },
    )
    assert verified.status_code == 200
    assert verified.json()["provider"] == "mock"


async def test_mock_subscription_persists_and_cancels(auth_client):
    initial = await auth_client.get("/api/billing/subscription")
    assert initial.status_code == 200
    assert initial.json()["plan_id"] == "free"
    assert initial.json()["status"] == "active"

    started = await auth_client.post(
        "/api/billing/otp/request", json={"plan_id": "plus"}
    )
    assert started.status_code == 201, started.text
    challenge = started.json()
    assert challenge["demo_otp"] == "1234"
    assert challenge["status_code"] == "S1000"

    wrong = await auth_client.post(
        "/api/billing/otp/verify",
        json={"challenge_id": challenge["challenge_id"], "otp": "9999"},
    )
    assert wrong.status_code == 400

    verified = await auth_client.post(
        "/api/billing/otp/verify",
        json={"challenge_id": challenge["challenge_id"], "otp": "1234"},
    )
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["plan_id"] == "plus"
    assert body["status"] == "active"
    assert body["provider"] == "mock"
    assert body["amount_bdt"] == 199

    persisted = await auth_client.get("/api/billing/subscription")
    assert persisted.status_code == 200
    assert persisted.json()["plan_id"] == "plus"

    upgrade_catalog = (await auth_client.get("/api/billing/plans")).json()
    pro = next(
        plan for plan in upgrade_catalog["results"] if plan["id"] == "pro"
    )
    assert pro["amount_bdt"] == 249

    upgrade_started = await auth_client.post(
        "/api/billing/otp/request", json={"plan_id": "pro"}
    )
    assert upgrade_started.status_code == 201
    upgraded = await auth_client.post(
        "/api/billing/otp/verify",
        json={
            "challenge_id": upgrade_started.json()["challenge_id"],
            "otp": "1234",
        },
    )
    assert upgraded.status_code == 200
    assert upgraded.json()["plan_id"] == "pro"
    assert upgraded.json()["amount_bdt"] == 249

    cancelled = await auth_client.post("/api/billing/subscription/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status_code"] == "S1000"
    assert cancelled.json()["subscription"]["status"] == "cancelled"

    after = await auth_client.get("/api/billing/subscription")
    assert after.json()["status"] == "cancelled"


async def test_mock_subscription_can_cancel_after_runtime_switches_to_bdapps(
    auth_client, monkeypatch
):
    started = await auth_client.post(
        "/api/billing/otp/request", json={"plan_id": "pro"}
    )
    verified = await auth_client.post(
        "/api/billing/otp/verify",
        json={
            "challenge_id": started.json()["challenge_id"],
            "otp": "1234",
        },
    )
    assert verified.status_code == 200
    assert verified.json()["provider"] == "mock"

    monkeypatch.setattr(settings, "BILLING_PROVIDER", "bdapps")
    cancelled = await auth_client.post("/api/billing/subscription/cancel")

    assert cancelled.status_code == 200
    assert cancelled.json()["subscription"]["status"] == "cancelled"
    assert cancelled.json()["subscription"]["provider"] == "mock"


async def test_server_rejects_free_plan_otp(auth_client):
    response = await auth_client.post(
        "/api/billing/otp/request", json={"plan_id": "free"}
    )
    assert response.status_code == 400


async def test_development_otp_has_no_cooldown(auth_client):
    first = await auth_client.post(
        "/api/billing/otp/request", json={"plan_id": "plus"}
    )
    assert first.status_code == 201

    second = await auth_client.post(
        "/api/billing/otp/request", json={"plan_id": "plus"}
    )
    assert second.status_code == 201
    assert second.json()["demo_otp"] == "1234"


async def test_billing_otp_request_has_carrier_cooldown(
    auth_client, monkeypatch
):
    class FakeBdAppsProvider:
        name = "bdapps"

        async def request_otp(self, subscriber_id):
            return OtpStartResult(
                reference_no=f"carrier-{subscriber_id}",
                status_code="S1000",
                status_detail="Success",
            )

    provider = FakeBdAppsProvider()

    def provider_for(plan_id, provider_name=None):
        assert plan_id == "plus"
        assert provider_name is None
        return provider

    monkeypatch.setattr(
        billing_router, "get_billing_provider", provider_for
    )

    first = await auth_client.post(
        "/api/billing/otp/request", json={"plan_id": "plus"}
    )
    assert first.status_code == 201

    second = await auth_client.post(
        "/api/billing/otp/request", json={"plan_id": "plus"}
    )
    assert second.status_code == 429


async def test_bdapps_masked_identity_is_reused_for_status_and_cancel(
    auth_client, monkeypatch
):
    class FakeBdAppsProvider:
        name = "bdapps"

        def __init__(self):
            self.status_subscribers = []
            self.cancel_subscribers = []

        async def request_otp(self, subscriber_id):
            assert subscriber_id == "tel:8801712345678"
            return OtpStartResult(
                reference_no="real-reference",
                status_code="S1000",
                status_detail="Success",
            )

        async def verify_otp(self, reference_no, otp):
            assert reference_no == "real-reference"
            assert otp == "5678"
            return SubscriptionResult(
                status_code="S1000",
                status_detail="Success",
                subscription_status="REGISTERED",
                subscriber_id=MASKED_SUBSCRIBER,
            )

        async def get_status(self, subscriber_id):
            self.status_subscribers.append(subscriber_id)
            return SubscriptionResult(
                status_code="S1000",
                status_detail="Success",
                subscription_status="REGISTERED",
                subscriber_id=subscriber_id,
            )

        async def unsubscribe(self, subscriber_id):
            self.cancel_subscribers.append(subscriber_id)
            return SubscriptionResult(
                status_code="S1000",
                status_detail="Success",
                subscription_status="UNREGISTERED",
                subscriber_id=subscriber_id,
            )

    provider = FakeBdAppsProvider()
    monkeypatch.setattr(settings, "BILLING_PROVIDER", "bdapps")

    def provider_for(plan_id, provider_name=None):
        assert plan_id == "plus"
        assert provider_name in (None, "bdapps")
        return provider

    monkeypatch.setattr(
        billing_router, "get_billing_provider", provider_for
    )

    started = await auth_client.post(
        "/api/billing/otp/request", json={"plan_id": "plus"}
    )
    assert started.status_code == 201
    verified = await auth_client.post(
        "/api/billing/otp/verify",
        json={
            "challenge_id": started.json()["challenge_id"],
            "otp": "5678",
        },
    )
    assert verified.status_code == 200
    assert verified.json()["subscriber_id"] == "01712345678"

    current = await auth_client.get("/api/billing/subscription")
    assert current.status_code == 200
    assert provider.status_subscribers == [MASKED_SUBSCRIBER]

    cancelled = await auth_client.post("/api/billing/subscription/cancel")
    assert cancelled.status_code == 200
    assert provider.cancel_subscribers == [MASKED_SUBSCRIBER]


async def test_bdapps_sms_callback_requires_matching_application(client, monkeypatch):
    monkeypatch.setattr(settings, "BDAPPS_PLUS_APPLICATION_ID", "APP_PLUS")
    monkeypatch.setattr(settings, "BDAPPS_PLUS_PASSWORD", "plus-secret")
    # Pro credentials are intentionally ignored: Pro is mock-only.
    monkeypatch.setattr(settings, "BDAPPS_PRO_APPLICATION_ID", "APP_PRO")
    monkeypatch.setattr(settings, "BDAPPS_PRO_PASSWORD", "pro-secret")
    payload = {
        "version": "1.0",
        "applicationId": "APP_PLUS",
        "sourceAddress": "tel:8801712345678",
        "message": "PLAN",
        "requestId": "sms-request-1",
        "encoding": "0",
    }

    accepted = await client.post("/api/bdapps/sms/receive", json=payload)
    assert accepted.status_code == 200
    assert accepted.json() == {
        "statusCode": "S1000",
        "statusDetail": "Request was successfully processed",
    }

    payload["applicationId"] = "APP_PRO"
    rejected_pro = await client.post("/api/bdapps/sms/receive", json=payload)
    assert rejected_pro.status_code == 403

    payload["applicationId"] = "APP_OTHER"
    rejected = await client.post("/api/bdapps/sms/receive", json=payload)
    assert rejected.status_code == 403


async def test_bdapps_notification_synchronizes_subscription(
    auth_client, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "BDAPPS_PLUS_APPLICATION_ID", "APP_PLUS")
    monkeypatch.setattr(settings, "BDAPPS_PLUS_PASSWORD", "plus-secret")
    notification = {
        "timeStamp": "2607241800",
        "version": "1.0",
        "applicationId": "APP_PLUS",
        "password": "plus-secret",
        "subscriberId": "tel:8801712345678",
        "frequency": "monthly",
        "status": "REGISTERED.",
    }

    registered = await auth_client.post(
        "/api/bdapps/subscription/notify", json=notification
    )
    assert registered.status_code == 200
    subscription = await auth_client.get("/api/billing/subscription")
    assert subscription.status_code == 200
    assert subscription.json()["plan_id"] == "plus"
    assert subscription.json()["status"] == "active"
    assert subscription.json()["provider"] == "bdapps"

    stored_result = await db_session.execute(select(Subscription))
    stored = stored_result.scalar_one()
    stored.subscriber_id = MASKED_SUBSCRIBER
    await db_session.commit()

    notification["subscriberId"] = MASKED_SUBSCRIBER
    notification["status"] = "UNREGISTERED."
    unregistered = await auth_client.post(
        "/api/bdapps/subscription/notify", json=notification
    )
    assert unregistered.status_code == 200
    subscription = await auth_client.get("/api/billing/subscription")
    assert subscription.json()["status"] == "cancelled"

    notification["password"] = "wrong"
    rejected = await auth_client.post(
        "/api/bdapps/subscription/notify", json=notification
    )
    assert rejected.status_code == 403


async def test_bdapps_pro_subscription_callback_is_rejected(
    auth_client, monkeypatch
):
    monkeypatch.setattr(settings, "BDAPPS_PLUS_APPLICATION_ID", "APP_PLUS")
    monkeypatch.setattr(settings, "BDAPPS_PLUS_PASSWORD", "plus-secret")
    monkeypatch.setattr(settings, "BDAPPS_PRO_APPLICATION_ID", "APP_PRO")
    monkeypatch.setattr(settings, "BDAPPS_PRO_PASSWORD", "pro-secret")

    pro_notification = {
        "timeStamp": "2607241800",
        "version": "1.0",
        "applicationId": "APP_PRO",
        "password": "pro-secret",
        "subscriberId": "tel:8801712345678",
        "frequency": "monthly",
        "status": "REGISTERED.",
    }
    rejected = await auth_client.post(
        "/api/bdapps/subscription/notify", json=pro_notification
    )
    assert rejected.status_code == 403
    subscription = await auth_client.get("/api/billing/subscription")
    assert subscription.json()["plan_id"] == "free"
    assert subscription.json()["status"] == "active"
