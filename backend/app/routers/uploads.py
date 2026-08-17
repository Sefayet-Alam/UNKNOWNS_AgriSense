"""File uploads: leaf photos (disease detection) + voice notes (accessibility).

One endpoint accepts either an image or an audio file, stores it user-scoped on
disk (Docker/local) or in Vercel Blob, and — for audio — transcribes it
immediately via Gemini so the voice note can flow through the normal text agent
pipeline. Images are read back later by the on-device disease classifier via
the ``classify_leaf_disease`` tool.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters.transcribe import TranscribeError, transcribe_audio
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Attachment, User
from ..storage import (
    StorageError,
    is_configured_blob_url,
    load_bytes,
    store_bytes,
)

log = logging.getLogger("agrisense.routers.uploads")

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

_EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
}


def _kind_for(mime: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=f"unsupported content type: {mime}",
    )


class CompletedBlobUpload(BaseModel):
    """A browser-to-Blob upload that the authenticated API should finalize."""

    url: str
    mime_type: str


async def _persist_attachment(
    *,
    user: User,
    db: AsyncSession,
    kind: str,
    mime: str,
    data: bytes,
    location: str,
) -> dict:
    transcript = None
    warning = None
    if kind == "audio":
        try:
            transcript = (await transcribe_audio(data, mime))["transcript"]
        except TranscribeError as exc:
            warning = f"transcription unavailable: {exc}"
            log.warning("voice-note transcription failed: %s", exc)

    row = Attachment(
        user_id=user.id,
        kind=kind,
        mime_type=mime,
        path=location,
        transcript=transcript,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    return {
        "id": row.id,
        "kind": row.kind,
        "mime_type": row.mime_type,
        "transcript": row.transcript,
        "warning": warning,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store a leaf photo or voice note; transcribe audio. Returns the record."""
    mime = (file.content_type or "").lower()
    kind = _kind_for(mime)
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty upload")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"file exceeds {settings.MAX_UPLOAD_MB} MB limit",
        )

    ext = _EXT_BY_MIME.get(mime) or (Path(file.filename or "").suffix.lstrip(".") or "bin")
    filename = f"{uuid.uuid4().hex}.{ext}"
    try:
        location = await store_bytes(
            user_id=user.id,
            filename=filename,
            data=data,
            mime_type=mime,
        )
    except StorageError as exc:
        log.error("upload storage failed: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "upload storage unavailable"
        ) from exc

    return await _persist_attachment(
        user=user,
        db=db,
        kind=kind,
        mime=mime,
        data=data,
        location=location,
    )


@router.post("/from-blob", status_code=status.HTTP_201_CREATED)
async def finalize_blob_upload(
    payload: CompletedBlobUpload,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Finalize a direct browser upload without crossing function body limits."""
    mime = payload.mime_type.lower()
    kind = _kind_for(mime)
    expected_prefix = f"/uploads/{user.id}/"
    if not is_configured_blob_url(payload.url) or not urlsplit(payload.url).path.startswith(
        expected_prefix
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid blob upload URL")
    try:
        data = await load_bytes(payload.url)
    except StorageError as exc:
        log.warning("uploaded Blob object unavailable: %s", exc)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "uploaded Blob object is unavailable"
        ) from exc
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty upload")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"file exceeds {settings.MAX_UPLOAD_MB} MB limit",
        )
    return await _persist_attachment(
        user=user,
        db=db,
        kind=kind,
        mime=mime,
        data=data,
        location=payload.url,
    )


@router.get("/{attachment_id}/content")
async def content(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream a user's own uploaded file back (e.g. to render a sent photo)."""
    row = (
        await db.execute(
            select(Attachment).where(
                Attachment.id == attachment_id, Attachment.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found")
    try:
        data = await load_bytes(row.path)
    except StorageError as exc:
        log.warning("attachment content unavailable (id=%s): %s", row.id, exc)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found") from exc
    return Response(content=data, media_type=row.mime_type)


@router.get("/{attachment_id}/blob-access")
async def blob_access(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return an owned private-Blob location for short-lived URL signing."""
    row = (
        await db.execute(
            select(Attachment).where(
                Attachment.id == attachment_id, Attachment.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if row is None or not is_configured_blob_url(row.path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "blob attachment not found")
    return {"url": row.path, "mime_type": row.mime_type}
