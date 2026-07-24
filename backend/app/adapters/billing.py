"""Billing providers: deterministic local mock and real BDApps subscription API."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import httpx

from ..config import settings


class BillingProviderError(RuntimeError):
    """Safe provider error that can be returned to an API client."""


@dataclass(frozen=True)
class OtpStartResult:
    reference_no: str
    status_code: str
    status_detail: str
    demo_otp: str | None = None


@dataclass(frozen=True)
class SubscriptionResult:
    status_code: str
    status_detail: str
    subscription_status: str
    subscriber_id: str = ""

    @property
    def ok(self) -> bool:
        return self.status_code == "S1000"


def bdapps_subscriber_id(phone: str) -> str:
    """Convert canonical 01XXXXXXXXX into BDApps' tel:8801… form."""
    return f"tel:88{phone}"


class MockBillingProvider:
    name = "mock"

    async def request_otp(self, subscriber_id: str) -> OtpStartResult:
        return OtpStartResult(
            reference_no=f"mock-{uuid4()}",
            status_code="S1000",
            status_detail="Demo OTP generated.",
            demo_otp=settings.MOCK_OTP_CODE,
        )

    async def verify_otp(
        self, reference_no: str, otp: str
    ) -> SubscriptionResult:
        if otp != settings.MOCK_OTP_CODE:
            return SubscriptionResult(
                status_code="E1312",
                status_detail="Invalid OTP.",
                subscription_status="UNREGISTERED",
            )
        return SubscriptionResult(
            status_code="S1000",
            status_detail="Subscription activated in demo mode.",
            subscription_status="REGISTERED",
        )

    async def get_status(self, subscriber_id: str) -> SubscriptionResult:
        return SubscriptionResult(
            status_code="S1000",
            status_detail="Demo subscription status loaded.",
            subscription_status="REGISTERED",
            subscriber_id=subscriber_id,
        )

    async def unsubscribe(self, subscriber_id: str) -> SubscriptionResult:
        return SubscriptionResult(
            status_code="S1000",
            status_detail="Subscription cancelled.",
            subscription_status="UNREGISTERED",
            subscriber_id=subscriber_id,
        )


class BdAppsBillingProvider:
    name = "bdapps"

    def __init__(self) -> None:
        if not settings.BDAPPS_APPLICATION_ID or not settings.BDAPPS_PASSWORD:
            raise BillingProviderError(
                "BDApps is enabled but its application credentials are missing."
            )

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{settings.BDAPPS_BASE_URL.rstrip('/')}{path}"
        body = {
            "applicationId": settings.BDAPPS_APPLICATION_ID,
            "password": settings.BDAPPS_PASSWORD,
            **payload,
        }
        try:
            async with httpx.AsyncClient(
                timeout=settings.BDAPPS_TIMEOUT_SECONDS
            ) as client:
                response = await client.post(
                    url,
                    json=body,
                    headers={"Content-Type": "application/json;charset=utf-8"},
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BillingProviderError(
                "BDApps is temporarily unavailable. Please try again."
            ) from exc
        if not isinstance(data, dict):
            raise BillingProviderError("BDApps returned an invalid response.")
        return data

    async def request_otp(self, subscriber_id: str) -> OtpStartResult:
        data = await self._post(
            "/otp/request", {"subscriberId": subscriber_id}
        )
        code = str(data.get("statusCode", ""))
        if code != "S1000" or not data.get("referenceNo"):
            raise BillingProviderError(
                str(data.get("statusDetail") or "BDApps could not send the OTP.")
            )
        return OtpStartResult(
            reference_no=str(data["referenceNo"]),
            status_code=code,
            status_detail=str(data.get("statusDetail", "Success")),
        )

    async def verify_otp(
        self, reference_no: str, otp: str
    ) -> SubscriptionResult:
        data = await self._post(
            "/otp/verify", {"referenceNo": reference_no, "otp": otp}
        )
        return SubscriptionResult(
            status_code=str(data.get("statusCode", "")),
            status_detail=str(data.get("statusDetail", "OTP verification failed.")),
            subscription_status=str(
                data.get("subscriptionStatus", "UNREGISTERED")
            ).rstrip("."),
            subscriber_id=str(data.get("subscriberId", "")),
        )

    async def get_status(self, subscriber_id: str) -> SubscriptionResult:
        data = await self._post(
            "/subscription/getStatus", {"subscriberId": subscriber_id}
        )
        return SubscriptionResult(
            status_code=str(data.get("statusCode", "")),
            status_detail=str(data.get("statusDetail", "Status query failed.")),
            subscription_status=str(
                data.get("subscriptionStatus", "UNREGISTERED")
            ).rstrip("."),
            subscriber_id=subscriber_id,
        )

    async def unsubscribe(self, subscriber_id: str) -> SubscriptionResult:
        data = await self._post(
            "/subscription/send",
            {"subscriberId": subscriber_id, "action": "0"},
        )
        return SubscriptionResult(
            status_code=str(data.get("statusCode", "")),
            status_detail=str(data.get("statusDetail", "Unsubscribe failed.")),
            subscription_status=str(
                data.get("subscriptionStatus", "UNREGISTERED")
            ).rstrip("."),
            subscriber_id=subscriber_id,
        )


def get_billing_provider():
    provider = settings.BILLING_PROVIDER.strip().lower()
    if provider == "mock":
        return MockBillingProvider()
    if provider == "bdapps":
        return BdAppsBillingProvider()
    raise BillingProviderError(
        "BILLING_PROVIDER must be either 'mock' or 'bdapps'."
    )
