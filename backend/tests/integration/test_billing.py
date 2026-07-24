"""Integration tests for persisted mock billing and subscriptions."""
from __future__ import annotations

import pytest

from app.config import settings

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def mock_billing_provider(monkeypatch):
    monkeypatch.setattr(settings, "BILLING_PROVIDER", "mock")
    monkeypatch.setattr(settings, "MOCK_OTP_CODE", "1234")


async def test_billing_requires_auth(client):
    assert (await client.get("/api/billing/plans")).status_code == 401
    assert (await client.get("/api/billing/subscription")).status_code == 401


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

    cancelled = await auth_client.post("/api/billing/subscription/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status_code"] == "S1000"
    assert cancelled.json()["subscription"]["status"] == "cancelled"

    after = await auth_client.get("/api/billing/subscription")
    assert after.json()["status"] == "cancelled"


async def test_server_rejects_free_plan_otp(auth_client):
    response = await auth_client.post(
        "/api/billing/otp/request", json={"plan_id": "free"}
    )
    assert response.status_code == 400


async def test_bdapps_sms_callback_requires_matching_application(client, monkeypatch):
    monkeypatch.setattr(settings, "BDAPPS_APPLICATION_ID", "APP_TEST")
    monkeypatch.setattr(settings, "BDAPPS_PASSWORD", "secret")
    payload = {
        "version": "1.0",
        "applicationId": "APP_TEST",
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

    payload["applicationId"] = "APP_OTHER"
    rejected = await client.post("/api/bdapps/sms/receive", json=payload)
    assert rejected.status_code == 403


async def test_bdapps_notification_synchronizes_subscription(
    auth_client, monkeypatch
):
    monkeypatch.setattr(settings, "BDAPPS_APPLICATION_ID", "APP_TEST")
    monkeypatch.setattr(settings, "BDAPPS_PASSWORD", "secret")
    monkeypatch.setattr(settings, "BDAPPS_PLAN_ID", "plus")
    notification = {
        "timeStamp": "2607241800",
        "version": "1.0",
        "applicationId": "APP_TEST",
        "password": "secret",
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
