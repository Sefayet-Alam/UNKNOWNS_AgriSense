"""Application logging: console + rotating file logs (info + error).

Layout (``settings.LOG_DIR``, gitignored, bind-mounted to the host by
docker-compose so logs survive rebuilds):

- ``logs/info.log``  — INFO and above: agent turns, graph events, every tool
  invocation with args/results (truncated), adapter calls, HTTP access.
- ``logs/error.log`` — ERROR and above with tracebacks.

Named loggers used across the app (grep-friendly):

- ``agrisense.agent``   — turn lifecycle, graph invocation, model messages
- ``agrisense.tools``   — every tool invocation (also mirrors ``_emit``)
- ``agrisense.adapters``— external HTTP adapters (weather, CZIS)
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys

from .config import settings

_FMT = "%(asctime)s %(levelname)-7s %(name)s :: %(message)s"
_DONE = False


def setup_logging() -> None:
    """Idempotent root-logger configuration. Called once at app startup."""
    global _DONE
    if _DONE:
        return
    _DONE = True

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    formatter = logging.Formatter(_FMT)

    root = logging.getLogger()
    root.setLevel(level)

    if os.environ.get("TESTING") or "pytest" in sys.modules or os.environ.get("VERCEL"):
        # Test runs share the bind-mounted log dir with the real app, while
        # Vercel Functions have a read-only filesystem. Both use console-only
        # logging (Vercel captures stdout/stderr in deployment logs).
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(formatter)
        root.addHandler(console)
        return

    os.makedirs(settings.LOG_DIR, exist_ok=True)

    info_file = logging.handlers.RotatingFileHandler(
        os.path.join(settings.LOG_DIR, "info.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    info_file.setLevel(level)
    info_file.setFormatter(formatter)
    root.addHandler(info_file)

    error_file = logging.handlers.RotatingFileHandler(
        os.path.join(settings.LOG_DIR, "error.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_file.setLevel(logging.ERROR)
    error_file.setFormatter(formatter)
    root.addHandler(error_file)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Tame noisy third-party loggers; keep httpx request lines (useful: they
    # show every outbound tool/LLM HTTP call).
    for noisy in ("httpcore", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("agrisense").info(
        "logging initialized (level=%s, dir=%s)", settings.LOG_LEVEL, settings.LOG_DIR
    )


def trunc(value: object, limit: int = 400) -> str:
    """Compact one-line repr for log lines (tool args/results can be huge)."""
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 12] + f"…(+{len(text) - limit} chars)"
