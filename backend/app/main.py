"""FastAPI application entrypoint."""
from __future__ import annotations

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
from .routers import auth as auth_router
from .routers import chat as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema creation and the pgvector extension are handled by Alembic
    # migrations (see migrations/ and entrypoint.sh), so startup does no
    # DDL. Nothing to set up here; just clean up the engine on shutdown.
    yield
    await engine.dispose()


app = FastAPI(title="Argi API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(chat_router.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
