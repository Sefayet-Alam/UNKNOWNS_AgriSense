"""Async SQLAlchemy engine, session factory, and declarative Base."""
from __future__ import annotations

import os

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings

_engine_options = {"echo": False, "pool_pre_ping": True}
if os.environ.get("VERCEL"):
    # Serverless instances are short-lived and scale horizontally. Neon supplies
    # a pooled endpoint; retaining a client-side SQLAlchemy pool in every warm
    # function can otherwise multiply idle connections unnecessarily.
    _engine_options["poolclass"] = NullPool

engine = create_async_engine(settings.DATABASE_URL, **_engine_options)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency yielding a request-scoped async session."""
    async with AsyncSessionLocal() as session:
        yield session
