"""Voice-note transcription via Gemini (Tier 2 accessibility).

Low-literacy farmers can send a spoken voice note instead of typing; this
adapter turns the audio into text (Bengali or English) that then flows through
the normal agent pipeline. Gemini transcribes natively in Bengali, so no
separate ASR service is needed.

Design mirrors the other adapters: an injectable client so tests run offline,
a typed ``TranscribeError`` sentinel, and no invention — a failure raises rather
than fabricating a transcript. The LLM here does one narrow job (speech->text);
the agentic reasoning still happens downstream on the transcribed text.
"""
from __future__ import annotations

import logging
from typing import Optional

from ..config import settings

log = logging.getLogger("agrisense.adapters.transcribe")

_TRANSCRIBE_PROMPT = (
    "You are a speech-to-text engine for a Bangladeshi farming assistant. "
    "Transcribe the attached voice note VERBATIM in its original language "
    "(usually Bengali or English). Output ONLY the transcript text with no "
    "quotes, labels, or commentary. If the audio is silent or unintelligible, "
    "output an empty string."
)


class TranscribeError(Exception):
    """Transcription provider unavailable or returned no usable text."""


def _build_client():
    if not settings.GEMINI_API_KEY:
        raise TranscribeError("GEMINI_API_KEY is not configured")
    try:
        from google import genai
    except Exception as exc:  # pragma: no cover - import guard
        raise TranscribeError(f"google-genai unavailable: {exc}") from exc
    return genai.Client(api_key=settings.GEMINI_API_KEY)


async def transcribe_audio(
    audio_bytes: bytes,
    mime_type: str,
    *,
    client=None,
) -> dict:
    """Transcribe a voice note to text. Returns ``{"transcript", "model", ...}``.

    ``client`` may be injected (tests); otherwise a Gemini client is built from
    ``GEMINI_API_KEY``. Raises ``TranscribeError`` on any provider failure so the
    caller degrades instead of inventing a transcript.
    """
    if not audio_bytes:
        raise TranscribeError("empty audio payload")
    cl = client or _build_client()
    try:
        from google.genai import types

        part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        response = await cl.aio.models.generate_content(
            model=settings.GEMINI_TRANSCRIBE_MODEL,
            contents=[part, _TRANSCRIBE_PROMPT],
        )
    except TranscribeError:
        raise
    except Exception as exc:
        raise TranscribeError(f"transcription request failed: {exc}") from exc

    transcript = (getattr(response, "text", None) or "").strip()
    return {
        "transcript": transcript,
        "model": settings.GEMINI_TRANSCRIBE_MODEL,
        "mime_type": mime_type,
        "provider": "gemini",
    }
