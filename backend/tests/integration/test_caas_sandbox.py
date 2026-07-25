"""Integration coverage for the BDApps-compatible local CaaS sandbox."""
from __future__ import annotations


async def test_caas_quote_and_confirmed_debit(auth_client):
    quote = await auth_client.get("/api/billing/caas/quote")
    assert quote.status_code == 200
    assert quote.json()["balance_bdt"] == 500
    assert quote.json()["amount_bdt"] == 199
    assert quote.json()["simulator"] is True

    rejected = await auth_client.post(
        "/api/billing/caas/debit",
        json={"product_id": "plus_subscription", "confirm": False},
    )
    assert rejected.status_code == 400

    paid = await auth_client.post(
        "/api/billing/caas/debit",
        json={"product_id": "plus_subscription", "confirm": True},
    )
    assert paid.status_code == 200, paid.text
    receipt = paid.json()
    assert receipt["status_code"] == "S1000"
    assert receipt["amount_bdt"] == 199
    assert receipt["balance_before_bdt"] == 500
    assert receipt["balance_after_bdt"] == 301
    assert receipt["request_trace"]["password"] == "[redacted]"
    assert receipt["request_trace"]["subscriberId"].startswith("tel:880")

    after = await auth_client.get("/api/billing/caas/quote")
    assert after.json()["balance_bdt"] == 301

    subscription = await auth_client.get("/api/billing/subscription")
    assert subscription.json()["plan_id"] == "plus"
    assert subscription.json()["provider_status"] == "SANDBOX_DIRECT_DEBIT"


async def test_caas_rejects_unknown_product(auth_client):
    response = await auth_client.post(
        "/api/billing/caas/debit",
        json={"product_id": "client_supplied_price", "confirm": True},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown CaaS sandbox product."
