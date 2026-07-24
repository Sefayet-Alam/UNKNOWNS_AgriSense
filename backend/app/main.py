"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .database import Base, engine

# Import models so they register on Base.metadata before create_all.
from . import models  # noqa: F401
from .routers import auth as auth_router
from .routers import chat as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # pgvector extension must exist before create_all builds Vector columns.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)
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
