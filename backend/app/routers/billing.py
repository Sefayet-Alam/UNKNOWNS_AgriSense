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
    configured_bdapps_plan_ids,
    effective_billing_provider_name,
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
PRO_UPGRADE_PRICE_BDT = 249


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
        # Provider-issued masked identities stay server-only.
        subscriber_id=phone,
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


def _provider_subscriber_id(
    subscription: Subscription, user_phone: str
) -> str:
    """Return the provider identity, upgrading legacy local-phone records."""

    stored = (subscription.subscriber_id or "").strip()
    if not stored or stored == user_phone:
        return bdapps_subscriber_id(user_phone)
    return stored


def _provider_or_502(
    plan_id: str,
    provider_name: str | None = None,
):
    try:
        return get_billing_provider(plan_id, provider_name)
    except BillingProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _is_plus_to_pro_upgrade(
    subscription: Subscription | None,
    target_plan_id: str,
) -> bool:
    return bool(
        subscription is not None
        and subscription.status == "active"
        and subscription.plan_id == "plus"
        and target_plan_id == "pro"
    )


@router.get("/plans", response_model=BillingPlansOut)
async def plans(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subscription = await _subscription_for(db, user.id)
    is_upgrade = _is_plus_to_pro_upgrade(subscription, "pro")
    provider = effective_billing_provider_name()
    if provider == "bdapps":
        subscribable_plan_ids = configured_bdapps_plan_ids()
        # A BDApps subscription application has a fixed recurring tariff.
        # The regular ৳499 Pro application cannot safely represent a ৳249
        # Plus-to-Pro upgrade.
        if is_upgrade:
            subscribable_plan_ids = [
                plan_id
                for plan_id in subscribable_plan_ids
                if plan_id != "pro"
            ]
    else:
        subscribable_plan_ids = [
            plan.id for plan in PLANS.values() if plan.id != "free"
        ]
    results = list(PLANS.values())
    if is_upgrade:
        results = [
            (
                plan.model_copy(update={"amount_bdt": PRO_UPGRADE_PRICE_BDT})
                if plan.id == "pro"
                else plan
            )
            for plan in results
        ]
    return BillingPlansOut(
        results=results,
        provider=provider,
        subscribable_plan_ids=subscribable_plan_ids,
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
            result = await get_billing_provider(
                subscription.plan_id,
                subscription.provider,
            ).get_status(
                _provider_subscriber_id(subscription, user.phone)
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

    current_subscription = await _subscription_for(db, user.id)
    is_upgrade = _is_plus_to_pro_upgrade(current_subscription, plan.id)
    if (
        current_subscription is not None
        and current_subscription.status == "active"
        and not is_upgrade
    ):
        if current_subscription.plan_id == plan.id:
            detail = "This plan is already active."
        else:
            detail = (
                "Cancel your active plan before subscribing to another plan."
            )
        raise HTTPException(status_code=409, detail=detail)

    provider = _provider_or_502(plan.id)
    if is_upgrade and provider.name == "bdapps":
        raise HTTPException(
            status_code=503,
            detail=(
                "The discounted Pro upgrade requires a separate ৳249 BDApps "
                "subscription application. Development upgrade remains available "
                "until carrier upgrade credentials are configured."
            ),
        )
    if provider.name == "bdapps":
        cooldown_started_at = _now() - timedelta(
            seconds=settings.OTP_REQUEST_COOLDOWN_SECONDS
        )
        recent_challenge_result = await db.execute(
            select(OtpChallenge.id)
            .where(
                OtpChallenge.user_id == user.id,
                OtpChallenge.purpose == "billing_subscription",
                OtpChallenge.created_at >= cooldown_started_at,
            )
            .limit(1)
        )
        if recent_challenge_result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=429,
                detail=(
                    "A carrier OTP was requested recently. Wait a minute "
                    "before requesting another."
                ),
            )

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
            "amount_bdt": (
                PRO_UPGRADE_PRICE_BDT if is_upgrade else plan.amount_bdt
            ),
            "billing_cycle": plan.billing_cycle,
            "subscriber_id": subscriber_id,
            "upgrade_from": "plus" if is_upgrade else "",
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

    details = challenge.details or {}
    plan_id = str(details.get("plan_id", ""))
    if plan_id not in PLANS or plan_id == "free":
        raise HTTPException(
            status_code=400, detail="OTP request has an invalid billing plan."
        )

    provider = _provider_or_502(plan_id)
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
    subscription = await _subscription_for(db, user.id)
    if subscription is None:
        subscription = Subscription(user_id=user.id)
        db.add(subscription)
    subscription.plan_id = str(details["plan_id"])
    subscription.status = "active"
    subscription.provider = challenge.provider
    subscription.provider_status = verified.subscription_status
    if challenge.provider == "bdapps":
        subscription.subscriber_id = (
            verified.subscriber_id.strip()
            or str(details["subscriber_id"])
        )
    else:
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

    provider = _provider_or_502(
        subscription.plan_id,
        subscription.provider,
    )
    if provider.name != subscription.provider:
        raise HTTPException(
            status_code=409,
            detail="Billing provider changed; cancellation could not be confirmed.",
        )
    try:
        result = await provider.unsubscribe(
            _provider_subscriber_id(subscription, user.phone)
        )
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
