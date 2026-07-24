"""Outbound SMS via bulksmsbd.net (proactive weather advisories).

Contract (per bulksmsbd docs):
- GET  {SMS_API_URL}?api_key=..&type=text&number=8801XXXXXXXXX&senderid=..&message=..
- The JSON reply's ``response_code`` is 202 on success; every other code is
  a provider-side rejection (e.g. 1031 = account has no sending access).

Design rules (mirrors adapters/weather.py):
- Injectable ``httpx.AsyncClient`` so tests run offline via MockTransport.
- A provider rejection is RETURNED as ``{"status": "failed", ...}`` — one
  farmer's failed delivery must never abort a whole scan. Only transport /
  malformed-response errors raise ``SmsError`` (also caught per-recipient
  by the scan job).
- ``settings.SMS_DRY_RUN`` short-circuits before any HTTP: the pipeline
  stays fully demoable while the bulksmsbd account awaits sending access.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..config import settings
from ..schemas import normalize_bd_phone

log = logging.getLogger("agrisense.adapters.sms")

TIMEOUT_S = 15.0
SUCCESS_CODE = 202


class SmsError(Exception):
    """Transport failure or unparseable provider response."""


def to_bd_msisdn(phone: str) -> str:
    """Canonical local ``01XXXXXXXXX`` -> bulksmsbd's ``8801XXXXXXXXX``."""
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

    params = {
        "api_key": settings.SMS_API_KEY,
        "type": "text",
        "number": number,
        "senderid": settings.SMS_SENDER_ID,
        "message": message,
    }
    owns = client is None
    cl = client or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        try:
            resp = await cl.get(settings.SMS_API_URL, params=params)
            payload = resp.json()
        except Exception as exc:  # transport error / non-JSON body
            raise SmsError(f"SMS transport failure: {exc}") from exc
    finally:
        if owns:
            await cl.aclose()

    code = payload.get("response_code")
    if code == SUCCESS_CODE:
        log.info("SMS sent to %s (response_code=202)", number)
        return {"status": "sent", "number": number, "response": payload}
    log.warning("SMS to %s rejected by provider: %s", number, payload)
    return {"status": "failed", "number": number, "response": payload}
