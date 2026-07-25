"""Best-effort live market-price fetch (Tier 2), with honest degradation.

Bangladesh has no clean public price API — DAM/TCB publish HTML only and are
flaky. So this adapter is *real-capable but optional*: if
``settings.MARKET_PRICE_API_URL`` is configured it attempts a live fetch;
otherwise (and on any failure) it raises ``MarketPriceError`` and the caller
falls back to the seeded historical snapshot. Same pattern as the weather/SMS
adapters: injectable client, typed sentinel, never invents a price.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..config import settings

log = logging.getLogger("agrisense.adapters.market_price")

TIMEOUT_S = 12.0


class MarketPriceError(Exception):
    """No live source configured, or the live fetch failed/was unparseable."""


async def fetch_live_price(
    crop: str, *, client: Optional[httpx.AsyncClient] = None
) -> dict:
    """Attempt a live current price for ``crop``. Raises on any failure.

    Returns ``{"crop", "price", "source", "date"}`` on success. Expects the
    configured endpoint to answer JSON ``{"price": <number>, "date": "YYYY-MM-DD"}``
    for ``?crop=<name>``; adapt the parser when wiring a real DAM/TCB feed.
    """
    url = settings.MARKET_PRICE_API_URL
    if not url:
        raise MarketPriceError("no live market-price source configured")
    owns = client is None
    cl = client or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        try:
            resp = await cl.get(url, params={"crop": crop})
            payload = resp.json()
            price = float(payload["price"])
        except Exception as exc:
            raise MarketPriceError(f"live market-price fetch failed: {exc}") from exc
    finally:
        if owns:
            await cl.aclose()
    if price <= 0:
        raise MarketPriceError("live source returned a non-positive price")
    return {
        "crop": crop,
        "price": round(price, 2),
        "date": payload.get("date"),
        "source": url,
    }
