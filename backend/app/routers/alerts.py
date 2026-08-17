"""Proactive weather alerts: manual scan trigger + per-user alert history.

The daily scan runs from the lifespan loop; this router exists so the scan
can be fired on demand (demo/judging) and so the frontend can show a
farmer's alert history without going through the agent.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select

from .. import database as db_module
from ..config import settings
from ..deps import get_current_user
from ..models import User, WeatherAlert
from ..services.weather_scan import run_weather_scan

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("/scan-now")
async def scan_now(user: User = Depends(get_current_user)):
    """Run one weather-scan pass immediately and return its report."""
    report = await run_weather_scan()
    return {"status": "completed", "report": report}


@router.get("/cron")
async def cron_scan(authorization: str | None = Header(default=None)):
    """Run the daily scan from Vercel Cron using its bearer secret.

    The existing authenticated ``scan-now`` endpoint remains available for
    farmers/demo operators. This route exists only because serverless runtimes
    cannot keep the container lifespan loop alive between requests.
    """
    if not settings.CRON_SECRET:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "cron secret is not configured"
        )
    expected = f"Bearer {settings.CRON_SECRET}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid cron authorization")
    report = await run_weather_scan()
    return {"status": "completed", "report": report}


@router.get("")
async def my_alerts(user: User = Depends(get_current_user)):
    """The calling farmer's recent alerts, newest first."""
    async with db_module.AsyncSessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(WeatherAlert)
                    .where(WeatherAlert.user_id == user.id)
                    .order_by(WeatherAlert.created_at.desc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
    return {
        "results": [
            {
                "id": row.id,
                "farm_id": row.farm_id,
                "alert_type": row.alert_type,
                "event_date": row.event_date.isoformat() if row.event_date else None,
                "trigger_date": row.trigger_date.isoformat(),
                "message": row.message,
                "sms_status": row.sms_status,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }
