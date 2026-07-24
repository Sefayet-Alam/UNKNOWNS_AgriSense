"""Integration tests for the file-upload endpoint (Tier 2)."""
from __future__ import annotations

import io

import pytest
from sqlalchemy import select

from app.models import Attachment
from app.routers import uploads as uploads_router


def _png_bytes():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (30, 150, 30)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _tmp_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads_router.settings, "UPLOAD_DIR", str(tmp_path))


@pytest.mark.asyncio
async def test_image_upload_stores_row_and_file(auth_client, db_session, tmp_path):
    resp = await auth_client.post(
        "/api/uploads",
        files={"file": ("leaf.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "image"
    assert body["transcript"] is None

    row = (
        await db_session.execute(select(Attachment).where(Attachment.id == body["id"]))
    ).scalar_one()
    assert row.kind == "image"
    assert row.mime_type == "image/png"
    from pathlib import Path

    assert Path(row.path).read_bytes()  # file actually written


@pytest.mark.asyncio
async def test_audio_upload_is_transcribed(auth_client, monkeypatch):
    async def fake_transcribe(data, mime, **kwargs):
        return {"transcript": "আমার আলু গাছে দাগ", "provider": "gemini"}

    monkeypatch.setattr(uploads_router, "transcribe_audio", fake_transcribe)
    resp = await auth_client.post(
        "/api/uploads",
        files={"file": ("note.mp3", b"fake-audio-bytes", "audio/mpeg")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "audio"
    assert body["transcript"] == "আমার আলু গাছে দাগ"
    assert body["warning"] is None


@pytest.mark.asyncio
async def test_audio_upload_survives_transcription_outage(auth_client, monkeypatch):
    async def boom(data, mime, **kwargs):
        raise uploads_router.TranscribeError("gemini down")

    monkeypatch.setattr(uploads_router, "transcribe_audio", boom)
    resp = await auth_client.post(
        "/api/uploads",
        files={"file": ("note.ogg", b"bytes", "audio/ogg")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["transcript"] is None
    assert "transcription unavailable" in body["warning"]


@pytest.mark.asyncio
async def test_unsupported_type_is_rejected(auth_client):
    resp = await auth_client.post(
        "/api/uploads",
        files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_oversized_upload_is_rejected(auth_client, monkeypatch):
    monkeypatch.setattr(uploads_router.settings, "MAX_UPLOAD_MB", 0)
    resp = await auth_client.post(
        "/api/uploads",
        files={"file": ("leaf.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_uploaded_image_can_be_fetched_back(auth_client):
    img = _png_bytes()
    up = await auth_client.post(
        "/api/uploads", files={"file": ("leaf.png", img, "image/png")}
    )
    aid = up.json()["id"]
    got = await auth_client.get(f"/api/uploads/{aid}/content")
    assert got.status_code == 200
    assert got.headers["content-type"].startswith("image/png")
    assert got.content == img


@pytest.mark.asyncio
async def test_content_missing_attachment_is_404(auth_client):
    resp = await auth_client.get("/api/uploads/999999/content")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_history_endpoint_preserves_message_attachments(auth_client, db_session):
    # The list-messages response_model must NOT strip the attachments field
    # (regression: photo showed live but vanished on history refetch).
    from sqlalchemy import select

    from app.models import ChatMessage, ChatSession, User

    user = (await db_session.execute(select(User))).scalar_one()
    session = ChatSession(user_id=user.id, title="t")
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    db_session.add(
        ChatMessage(
            session_id=session.id,
            role="user",
            content="check this leaf",
            tool_trace=[],
            attachments=[{"id": 7, "kind": "image", "mime_type": "image/png"}],
        )
    )
    await db_session.commit()

    resp = await auth_client.get(f"/api/chat/sessions/{session.id}/messages")
    assert resp.status_code == 200
    msg = resp.json()["results"][0]
    assert msg["attachments"] == [{"id": 7, "kind": "image", "mime_type": "image/png"}]


@pytest.mark.asyncio
async def test_upload_requires_auth(client):
    resp = await client.post(
        "/api/uploads",
        files={"file": ("leaf.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 401
