"""Offline tests for the bulksmsbd SMS adapter (MockTransport, no network)."""
from __future__ import annotations

import httpx
import pytest

from app.adapters import sms as sms_mod


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_msisdn_conversion_accepts_every_stored_format():
    assert sms_mod.to_bd_msisdn("01712345678") == "8801712345678"
    assert sms_mod.to_bd_msisdn("+8801712345678") == "8801712345678"
    assert sms_mod.to_bd_msisdn("8801712345678") == "8801712345678"
    with pytest.raises(ValueError):
        sms_mod.to_bd_msisdn("12345")


@pytest.mark.asyncio
async def test_dry_run_short_circuits_with_zero_http_calls(monkeypatch):
    monkeypatch.setattr(sms_mod.settings, "SMS_DRY_RUN", True)

    def explode(request):  # any HTTP call is a test failure
        raise AssertionError("dry-run must not perform HTTP")

    result = await sms_mod.send_sms(
        "01712345678", "hello", client=_client(explode)
    )
    assert result == {
        "status": "dry_run",
        "number": "8801712345678",
        "response": None,
    }


@pytest.mark.asyncio
async def test_202_response_is_sent_and_params_are_correct(monkeypatch):
    monkeypatch.setattr(sms_mod.settings, "SMS_DRY_RUN", False)
    monkeypatch.setattr(sms_mod.settings, "SMS_API_KEY", "test-key")
    monkeypatch.setattr(sms_mod.settings, "SMS_SENDER_ID", "8809617000000")
    captured = {}

    def handler(request):
        captured.update(dict(request.url.params))
        return httpx.Response(
            200, json={"response_code": 202, "success_message": "SMS Submitted"}
        )

    result = await sms_mod.send_sms(
        "01919030974", "Test alert", client=_client(handler)
    )
    assert result["status"] == "sent"
    assert result["response"]["response_code"] == 202
    assert captured == {
        "api_key": "test-key",
        "type": "text",
        "number": "8801919030974",
        "senderid": "8809617000000",
        "message": "Test alert",
    }


@pytest.mark.asyncio
async def test_provider_rejection_is_returned_not_raised(monkeypatch):
    # 1031 is the real "no access" code the account currently returns —
    # it must be recorded as a failure, never crash the scan.
    monkeypatch.setattr(sms_mod.settings, "SMS_DRY_RUN", False)

    def handler(request):
        return httpx.Response(
            200,
            json={
                "response_code": 1031,
                "error_message": "You have no access for SMS Sending.",
            },
        )

    result = await sms_mod.send_sms("01712345678", "x", client=_client(handler))
    assert result["status"] == "failed"
    assert result["response"]["response_code"] == 1031


@pytest.mark.asyncio
async def test_transport_error_and_non_json_body_raise_smserror(monkeypatch):
    monkeypatch.setattr(sms_mod.settings, "SMS_DRY_RUN", False)

    def network_down(request):
        raise httpx.ConnectError("boom")

    with pytest.raises(sms_mod.SmsError):
        await sms_mod.send_sms("01712345678", "x", client=_client(network_down))

    def html_page(request):
        return httpx.Response(200, text="<html>gateway error</html>")

    with pytest.raises(sms_mod.SmsError):
        await sms_mod.send_sms("01712345678", "x", client=_client(html_page))
