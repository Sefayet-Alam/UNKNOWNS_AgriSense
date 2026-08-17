"""Vercel's conventional FastAPI entrypoint.

The application remains implemented in ``app.main``; this module only exposes
the existing ASGI app at a path Vercel detects without custom configuration.
"""

from app.main import app

__all__ = ["app"]
