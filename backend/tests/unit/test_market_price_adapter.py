"""Offline tests for the best-effort live market-price adapter (Tier 2)."""
from __future__ import annotations

import httpx
import pytest

from app.adapters import market_price as mp_api


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_no_url_configured_raises(monkeypatch):
    monkeypatch.setattr(mp_api.settings, "MARKET_PRICE_API_URL", "")
    with pytest.raises(mp_api.MarketPriceError):
        await mp_api.fetch_live_price("potato")


@pytest.mark.asyncio
async def test_live_success_returns_price(monkeypatch):
    monkeypatch.setattr(mp_api.settings, "MARKET_PRICE_API_URL", "https://dam.example/price")

    def handler(request):
        assert dict(request.url.params)["crop"] == "Potato"
        return httpx.Response(200, json={"price": 31.5, "date": "2026-07-25"})

    out = await mp_api.fetch_live_price("Potato", client=_client(handler))
    assert out["price"] == 31.5
    assert out["date"] == "2026-07-25"


@pytest.mark.asyncio
async def test_live_failure_raises(monkeypatch):
    monkeypatch.setattr(mp_api.settings, "MARKET_PRICE_API_URL", "https://dam.example/price")

    def boom(request):
        raise httpx.ConnectError("down")

    with pytest.raises(mp_api.MarketPriceError):
        await mp_api.fetch_live_price("potato", client=_client(boom))
