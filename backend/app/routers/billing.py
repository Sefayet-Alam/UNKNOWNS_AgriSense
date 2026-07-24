"""Authenticated plans, OTP activation, subscription status and cancellation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters.billing import (
    BillingProviderError,
    bdapps_subscriber_id,
    get_billing_provider,
)
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import OtpChallenge, Subscription, User
from ..schemas import (
    BillingCancelOut,
    BillingOtpStartOut,
    BillingOtpStartRequest,
    BillingOtpVerifyRequest,
    BillingPlanOut,
    BillingPlansOut,
    SubscriptionOut,
)
from ..security import hash_password, verify_password

router = APIRouter(prefix="/api/billing", tags=["billing"])

PLANS = {
    "free": BillingPlanOut(
        id="free",
        name="Free",
        amount_bdt=0,
        billing_cycle="none",
        features=[
            "Standard model",
            "Core plan, weather and crop advice",
            "Saved chat history",
        ],
    ),
    "plus": BillingPlanOut(
        id="plus",
        name="Plus",
        amount_bdt=199,
        billing_cycle="monthly",
        features=[
            "Faster model",
            "Deeper reasoning",
            "Priority weather refresh",
            "Scenario what-ifs",
        ],
    ),
    "pro": BillingPlanOut(
        id="pro",
        name="Pro",
        amount_bdt=499,
        billing_cycle="monthly",
        features=[
            "Best model and longest thinking",
            "Leaf-photo disease detection",
            "Market price alerts",
            "BDApps payments",
        ],
    ),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _subscription_out(
    subscription: Subscription | None, phone: str
) -> SubscriptionOut:
    if subscription is None:
        return SubscriptionOut(
            plan_id="free",
            status="active",
            provider="internal",
            provider_status="FREE",
            subscriber_id=phone,
            amount_bdt=0,
            billing_cycle="none",
        )
    return SubscriptionOut(
        plan_id=subscription.plan_id,
        status=subscription.status,
        provider=subscription.provider,
        provider_status=subscription.provider_status,
        subscriber_id=subscription.subscriber_id or phone,
        amount_bdt=subscription.amount_bdt,
        billing_cycle=subscription.billing_cycle,
        started_at=subscription.started_at,
        cancelled_at=subscription.cancelled_at,
    )


async def _subscription_for(
    db: AsyncSession, user_id: int
) -> Subscription | None:
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()


def _provider_or_502():
    try:
        return get_billing_provider()
    except BillingProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/plans", response_model=BillingPlansOut)
async def plans(user: User = Depends(get_current_user)):
    del user
    return BillingPlansOut(
        results=list(PLANS.values()),
        provider=settings.BILLING_PROVIDER.strip().lower(),
    )


@router.get("/subscription", response_model=SubscriptionOut)
async def subscription_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subscription = await _subscription_for(db, user.id)
    if (
        subscription is not None
        and subscription.provider == "bdapps"
        and subscription.status == "active"
    ):
        try:
            result = await get_billing_provider().get_status(
                bdapps_subscriber_id(user.phone)
            )
            if result.ok:
                registered = (
                    result.subscription_status.upper().rstrip(".") == "REGISTERED"
                )
                subscription.provider_status = result.subscription_status
                subscription.status = "active" if registered else "inactive"
                await db.commit()
                await db.refresh(subscription)
        except BillingProviderError:
            # Keep the last confirmed local state when status polling fails.
            pass
    return _subscription_out(subscription, user.phone)


@router.post(
    "/otp/request",
    response_model=BillingOtpStartOut,
    status_code=status.HTTP_201_CREATED,
)
async def request_billing_otp(
    payload: BillingOtpStartRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = PLANS.get(payload.plan_id)
    if plan is None or plan.id == "free":
        raise HTTPException(status_code=400, detail="Choose a paid plan.")

    provider_name = settings.BILLING_PROVIDER.strip().lower()
    if provider_name == "bdapps" and plan.id != settings.BDAPPS_PLAN_ID:
        raise HTTPException(
            status_code=400,
            detail=(
                f"This BDApps application is provisioned for the "
                f"{settings.BDAPPS_PLAN_ID} plan."
            ),
        )

    provider = _provider_or_502()
    subscriber_id = bdapps_subscriber_id(user.phone)
    try:
        result = await provider.request_otp(subscriber_id)
    except BillingProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    challenge = OtpChallenge(
        id=str(uuid4()),
        user_id=user.id,
        purpose="billing_subscription",
        provider=provider.name,
        provider_reference=result.reference_no,
        otp_hash=(
            hash_password(settings.MOCK_OTP_CODE)
            if provider.name == "mock"
            else ""
        ),
        details={
            "plan_id": plan.id,
            "amount_bdt": plan.amount_bdt,
            "billing_cycle": plan.billing_cycle,
            "subscriber_id": subscriber_id,
        },
        attempts=0,
        expires_at=_now() + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    db.add(challenge)
    await db.commit()

    return BillingOtpStartOut(
        challenge_id=challenge.id,
        expires_in_seconds=settings.OTP_TTL_SECONDS,
        status_code=result.status_code,
        status_detail=result.status_detail,
        demo_otp=result.demo_otp,
    )


@router.post("/otp/verify", response_model=SubscriptionOut)
async def verify_billing_otp(
    payload: BillingOtpVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OtpChallenge).where(
            OtpChallenge.id == payload.challenge_id,
            OtpChallenge.user_id == user.id,
            OtpChallenge.purpose == "billing_subscription",
        )
    )
    challenge = result.scalar_one_or_none()
    if challenge is None or challenge.verified_at is not None:
        raise HTTPException(status_code=400, detail="Invalid or used OTP request.")
    if challenge.expires_at <= _now():
        raise HTTPException(status_code=400, detail="OTP expired. Request a new one.")
    if challenge.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429, detail="Too many OTP attempts. Request a new one."
        )

    challenge.attempts += 1
    if challenge.provider == "mock" and not verify_password(
        payload.otp, challenge.otp_hash
    ):
        await db.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    provider = _provider_or_502()
    if provider.name != challenge.provider:
        raise HTTPException(
            status_code=409,
            detail="Billing provider changed. Request a new OTP.",
        )
    try:
        verified = await provider.verify_otp(
            challenge.provider_reference, payload.otp
        )
    except BillingProviderError as exc:
        await db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not verified.ok or (
        verified.subscription_status.upper().rstrip(".") != "REGISTERED"
    ):
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"{verified.status_detail} ({verified.status_code})",
        )

    challenge.verified_at = _now()
    details = challenge.details or {}
    subscription = await _subscription_for(db, user.id)
    if subscription is None:
        subscription = Subscription(user_id=user.id)
        db.add(subscription)
    subscription.plan_id = str(details["plan_id"])
    subscription.status = "active"
    subscription.provider = challenge.provider
    subscription.provider_status = verified.subscription_status
    subscription.subscriber_id = user.phone
    subscription.amount_bdt = int(details["amount_bdt"])
    subscription.billing_cycle = str(details["billing_cycle"])
    subscription.started_at = _now()
    subscription.cancelled_at = None
    await db.commit()
    await db.refresh(subscription)
    return _subscription_out(subscription, user.phone)


@router.post("/subscription/cancel", response_model=BillingCancelOut)
async def cancel_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subscription = await _subscription_for(db, user.id)
    if subscription is None or subscription.status != "active":
        raise HTTPException(status_code=400, detail="No active paid subscription.")

    provider = _provider_or_502()
    if provider.name != subscription.provider:
        raise HTTPException(
            status_code=409,
            detail="Billing provider changed; cancellation could not be confirmed.",
        )
    try:
        result = await provider.unsubscribe(bdapps_subscriber_id(user.phone))
    except BillingProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not result.ok:
        raise HTTPException(
            status_code=400,
            detail=f"{result.status_detail} ({result.status_code})",
        )

    subscription.status = "cancelled"
    subscription.provider_status = result.subscription_status
    subscription.cancelled_at = _now()
    await db.commit()
    await db.refresh(subscription)
    return BillingCancelOut(
        subscription=_subscription_out(subscription, user.phone),
        status_code=result.status_code,
        status_detail=result.status_detail,
    )
