"""Vercel Python Function exposing the existing FastAPI application."""

from app.main import app

__all__ = ["app"]
