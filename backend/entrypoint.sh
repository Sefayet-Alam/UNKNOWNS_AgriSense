#!/bin/sh
# Container entrypoint: migrate, ensure the committed RAG corpus, then serve.
#
# Alembic (migrations/env.py) reads DATABASE_URL from app.config.settings and
# also creates the pgvector extension inside the first migration, so no DDL
# runs in the app itself anymore.
set -e

echo "[entrypoint] Running database migrations (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] Ensuring committed RAG seed is present..."
python -m scripts.seed_rag_data --if-needed

echo "[entrypoint] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
