"""Public callbacks used by the BDApps platform."""
from __future__ import annotations

import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models import Subscription, User
from .billing import PLANS

router = APIRouter(prefix="/api/bdapps", tags=["bdapps"])
logger = logging.getLogger(__name__)


class BdAppsPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class SmsReceiveIn(BdAppsPayload):
    version: str
    application_id: str = Field(alias="applicationId")
    source_address: str = Field(alias="sourceAddress")
    message: str
    request_id: str = Field(alias="requestId")
    encoding: str


class SubscriptionNotificationIn(BdAppsPayload):
    time_stamp: str = Field(alias="timeStamp")
    version: str
    application_id: str = Field(alias="applicationId")
    password: str
    subscriber_id: str = Field(alias="subscriberId")
    frequency: str
    status: str


class BdAppsAck(BdAppsPayload):
    status_code: str = Field(alias="statusCode")
    status_detail: str = Field(alias="statusDetail")


def _require_bdapps_credentials(
    application_id: str, password: str | None = None
) -> None:
    if not settings.BDAPPS_APPLICATION_ID:
        raise HTTPException(
            status_code=503,
            detail="BDApps application credentials are not configured.",
        )
    app_matches = hmac.compare_digest(
        application_id, settings.BDAPPS_APPLICATION_ID
    )
    password_matches = password is None or (
        bool(settings.BDAPPS_PASSWORD)
        and hmac.compare_digest(password, settings.BDAPPS_PASSWORD)
    )
    if not app_matches or not password_matches:
        raise HTTPException(status_code=403, detail="Invalid BDApps callback.")


def _canonical_phone(subscriber_id: str) -> str | None:
    raw = subscriber_id.strip()
    if raw.lower().startswith("tel:"):
        raw = raw[4:]
    digits = "".join(character for character in raw if character.isdigit())
    if len(digits) == 13 and digits.startswith("8801"):
        return digits[2:]
    if len(digits) == 11 and digits.startswith("01"):
        return digits
    return None


def _ack(detail: str = "Request was successfully processed") -> BdAppsAck:
    return BdAppsAck(status_code="S1000", status_detail=detail)


@router.post("/sms/receive", response_model=BdAppsAck)
async def receive_sms(payload: SmsReceiveIn) -> BdAppsAck:
    """Acknowledge inbound SMS delivery from BDApps.

    AgriSense does not use SMS text as an application command. Keeping this
    endpoint deliberately side-effect free satisfies the BDApps message
    receiving contract without persisting private message content.
    """

    _require_bdapps_credentials(payload.application_id)
    logger.info(
        "BDApps inbound SMS acknowledged (request_id=%s, encoding=%s)",
        payload.request_id,
        payload.encoding,
    )
    return _ack()


@router.post("/subscription/notify", response_model=BdAppsAck)
async def subscription_notification(
    payload: SubscriptionNotificationIn,
    db: AsyncSession = Depends(get_db),
) -> BdAppsAck:
    """Synchronize asynchronous BDApps registration changes into Postgres."""

    _require_bdapps_credentials(payload.application_id, payload.password)
    phone = _canonical_phone(payload.subscriber_id)
    if phone is None:
        # Masked subscriber identifiers cannot be joined to a local account.
        # Acknowledge them so BDApps does not retry indefinitely.
        logger.warning("BDApps subscription notification had a masked subscriber")
        return _ack()

    user_result = await db.execute(select(User).where(User.phone == phone))
    user = user_result.scalar_one_or_none()
    if user is None:
        logger.warning("BDApps subscription notification had no local user")
        return _ack()

    subscription_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = subscription_result.scalar_one_or_none()
    provider_status = payload.status.upper().rstrip(".")
    now = datetime.now(timezone.utc)

    if provider_status == "REGISTERED":
        plan = PLANS.get(settings.BDAPPS_PLAN_ID)
        if plan is None or plan.id == "free":
            logger.error("BDAPPS_PLAN_ID does not identify a paid plan")
            return _ack()
        if subscription is None:
            subscription = Subscription(user_id=user.id)
            db.add(subscription)
        subscription.plan_id = plan.id
        subscription.status = "active"
        subscription.provider = "bdapps"
        subscription.provider_status = provider_status
        subscription.subscriber_id = user.phone
        subscription.amount_bdt = plan.amount_bdt
        subscription.billing_cycle = payload.frequency.lower()
        subscription.started_at = subscription.started_at or now
        subscription.cancelled_at = None
    elif provider_status == "UNREGISTERED" and subscription is not None:
        subscription.status = "cancelled"
        subscription.provider_status = provider_status
        subscription.cancelled_at = now
    elif subscription is not None:
        subscription.status = "inactive"
        subscription.provider_status = provider_status

    await db.commit()
    return _ack()
