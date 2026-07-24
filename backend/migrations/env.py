"""Alembic async migration environment for the Argi backend.

- Uses ``settings.DATABASE_URL`` (asyncpg DSN) as the connection source.
- ``target_metadata = Base.metadata`` with all models imported so autogenerate
  sees every table.
- Runs migrations through the async engine via ``connection.run_sync``.
- ``compare_type=True`` so column type changes are detected on autogenerate.
- Renders ``pgvector.sqlalchemy.Vector`` columns correctly for autogenerate.
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import pgvector's Vector so autogenerate can render Vector columns and so
# the type is importable from generated migrations.
from pgvector.sqlalchemy import Vector  # noqa: F401

from app.config import settings
from app.database import Base

# Importing the models module registers every table on Base.metadata.
from app import models  # noqa: F401

# ---- Alembic config --------------------------------------------------------- #
config = context.config

# Inject the runtime DSN from settings (env.py is the single source of truth).
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """Teach autogenerate how to emit pgvector ``Vector`` columns."""
    if type_ == "type" and isinstance(obj, Vector):
        autogen_context.imports.add("import pgvector.sqlalchemy")
        dim = getattr(obj, "dim", None)
        return f"pgvector.sqlalchemy.Vector(dim={dim})"
    # Fall back to Alembic's default rendering.
    return False


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations through run_sync."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (--sql mode)."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
