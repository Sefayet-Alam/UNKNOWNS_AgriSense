"""Configuration normalization for managed/serverless providers."""

from app.config import normalize_database_url


def test_neon_database_url_is_normalized_for_asyncpg():
    value = (
        "postgresql://user:secret@example.neon.tech/agrisense"
        "?sslmode=require&channel_binding=require"
    )
    assert normalize_database_url(value) == (
        "postgresql+asyncpg://user:secret@example.neon.tech/agrisense?ssl=require"
    )


def test_docker_asyncpg_database_url_is_unchanged():
    value = "postgresql+asyncpg://argi:secret@db:5432/argi"
    assert normalize_database_url(value) == value


def test_legacy_postgres_scheme_is_supported():
    assert normalize_database_url("postgres://u:p@host/db") == (
        "postgresql+asyncpg://u:p@host/db"
    )
