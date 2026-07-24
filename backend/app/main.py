"""FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import engine
from .logging_setup import setup_logging

setup_logging()

# Import models so they register on Base.metadata (used by Alembic autogenerate
# and by the test-suite's create_all). Schema is now owned by Alembic
# migrations, run at container start via entrypoint.sh — NOT here.
from . import models  # noqa: F401
from .routers import alerts as alerts_router
from .routers import auth as auth_router
from .routers import bdapps as bdapps_router
from .routers import billing as billing_router
from .routers import chat as chat_router
from .routers import geo as geo_router
from .routers import uploads as uploads_router

log = logging.getLogger("agrisense.main")

# Give the container (and its first migrations/requests) a moment before the
# first proactive scan; subsequent passes follow the configured interval.
_SCAN_STARTUP_DELAY_S = 30


async def _weather_scan_loop() -> None:
    from .services.weather_scan import run_weather_scan

    await asyncio.sleep(_SCAN_STARTUP_DELAY_S)
    while True:
        try:
            await run_weather_scan()
        except Exception as exc:  # a failed pass must never kill the app
            log.exception("weather scan pass failed: %s", exc)
        await asyncio.sleep(settings.WEATHER_SCAN_INTERVAL_HOURS * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema creation and the pgvector extension are handled by Alembic
    # migrations (see migrations/ and entrypoint.sh), so startup does no
    # DDL. The only startup work is the proactive weather-scan loop
    # (disabled under TESTING so the suite stays offline/deterministic).
    scan_task: asyncio.Task | None = None
    if settings.WEATHER_SCAN_ENABLED and not os.environ.get("TESTING"):
        scan_task = asyncio.create_task(_weather_scan_loop())
        log.info(
            "proactive weather scan enabled (every %sh, first pass in %ss)",
            settings.WEATHER_SCAN_INTERVAL_HOURS,
            _SCAN_STARTUP_DELAY_S,
        )
    yield
    if scan_task is not None:
        scan_task.cancel()
    await engine.dispose()


app = FastAPI(title="Argi API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(alerts_router.router)
app.include_router(auth_router.router)
app.include_router(bdapps_router.router)
app.include_router(billing_router.router)
app.include_router(chat_router.router)
app.include_router(geo_router.router)
app.include_router(uploads_router.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
