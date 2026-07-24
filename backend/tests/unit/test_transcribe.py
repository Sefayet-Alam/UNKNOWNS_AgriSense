"""Offline tests for the Gemini voice-note transcription adapter (Tier 2)."""
from __future__ import annotations

import pytest

from app.adapters import transcribe as tr


class _FakeModels:
    def __init__(self, text=None, exc=None):
        self._text = text
        self._exc = exc
        self.calls = []

    async def generate_content(self, model, contents):
        self.calls.append((model, contents))
        if self._exc:
            raise self._exc
        return type("Resp", (), {"text": self._text})()


class _FakeClient:
    def __init__(self, text=None, exc=None):
        self.aio = type("Aio", (), {"models": _FakeModels(text=text, exc=exc)})()


@pytest.mark.asyncio
async def test_transcribes_audio_to_text():
    client = _FakeClient(text="  আমার ধান খেতে পোকা লেগেছে  ")
    out = await tr.transcribe_audio(b"audiobytes", "audio/mp3", client=client)
    assert out["transcript"] == "আমার ধান খেতে পোকা লেগেছে"
    assert out["provider"] == "gemini"
    # the audio part and the prompt are both sent
    model, contents = client.aio.models.calls[0]
    assert len(contents) == 2


@pytest.mark.asyncio
async def test_empty_audio_raises():
    with pytest.raises(tr.TranscribeError):
        await tr.transcribe_audio(b"", "audio/mp3", client=_FakeClient(text="x"))


@pytest.mark.asyncio
async def test_provider_error_becomes_transcribe_error():
    client = _FakeClient(exc=RuntimeError("gemini 500"))
    with pytest.raises(tr.TranscribeError):
        await tr.transcribe_audio(b"bytes", "audio/ogg", client=client)


@pytest.mark.asyncio
async def test_missing_api_key_raises_when_no_client(monkeypatch):
    monkeypatch.setattr(tr.settings, "GEMINI_API_KEY", "")
    with pytest.raises(tr.TranscribeError):
        await tr.transcribe_audio(b"bytes", "audio/mp3")


@pytest.mark.asyncio
async def test_silent_audio_returns_empty_transcript():
    out = await tr.transcribe_audio(b"bytes", "audio/wav", client=_FakeClient(text=""))
    assert out["transcript"] == ""
