"""Outbound SMS via sms.net.bd (proactive weather advisories).

Contract (per sms.net.bd docs):
- POST {SMS_API_URL} form fields: api_key, msg, to (comma-separated
  ``8801XXXXXXXXX`` numbers), optional sender_id.
- The JSON reply's ``error`` is 0 on success (``data.request_id`` present);
  any non-zero ``error`` is a provider-side rejection with ``msg``.

Design rules (mirrors adapters/weather.py):
- Injectable ``httpx.AsyncClient`` so tests run offline via MockTransport.
- A provider rejection is RETURNED as ``{"status": "failed", ...}`` — one
  farmer's failed delivery must never abort a whole scan. Only transport /
  malformed-response errors raise ``SmsError`` (also caught per-recipient
  by the scan job).
- ``settings.SMS_DRY_RUN`` short-circuits before any HTTP so the pipeline
  stays fully demoable / test-safe without spending SMS credit.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..config import settings
from ..schemas import normalize_bd_phone

log = logging.getLogger("agrisense.adapters.sms")

TIMEOUT_S = 20.0
SUCCESS_ERROR = 0


class SmsError(Exception):
    """Transport failure or unparseable provider response."""


def to_bd_msisdn(phone: str) -> str:
    """Canonical local ``01XXXXXXXXX`` -> sms.net.bd's ``8801XXXXXXXXX``."""
    return "88" + normalize_bd_phone(phone)


async def send_sms(
    phone: str,
    message: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """Send one SMS. Returns ``{"status": "sent"|"failed"|"dry_run", ...}``.

    ``phone`` accepts any format ``normalize_bd_phone`` accepts. The raw
    provider JSON is included under ``response`` for the audit log.
    """
    number = to_bd_msisdn(phone)
    if settings.SMS_DRY_RUN:
        log.info("SMS dry-run to %s: %s", number, message)
        return {"status": "dry_run", "number": number, "response": None}

    data = {
        "api_key": settings.SMS_API_KEY,
        "msg": message,
        "to": number,
    }
    if settings.SMS_SENDER_ID:
        data["sender_id"] = settings.SMS_SENDER_ID
    owns = client is None
    cl = client or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        try:
            resp = await cl.post(settings.SMS_API_URL, data=data)
            payload = resp.json()
        except Exception as exc:  # transport error / non-JSON body
            raise SmsError(f"SMS transport failure: {exc}") from exc
    finally:
        if owns:
            await cl.aclose()

    if payload.get("error") == SUCCESS_ERROR:
        request_id = (payload.get("data") or {}).get("request_id")
        log.info("SMS sent to %s (request_id=%s)", number, request_id)
        return {"status": "sent", "number": number, "response": payload}
    log.warning("SMS to %s rejected by provider: %s", number, payload)
    return {"status": "failed", "number": number, "response": payload}
