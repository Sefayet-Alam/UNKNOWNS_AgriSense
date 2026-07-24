"""File uploads: leaf photos (disease detection) + voice notes (accessibility).

One endpoint accepts either an image or an audio file, stores it user-scoped on
disk, and — for audio — transcribes it immediately via Gemini so the voice note
can flow through the normal text agent pipeline. Images are read back later by
the on-device disease classifier via the ``classify_leaf_disease`` tool.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters.transcribe import TranscribeError, transcribe_audio
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Attachment, User

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
    user_dir = Path(settings.UPLOAD_DIR) / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / f"{uuid.uuid4().hex}.{ext}"
    dest.write_bytes(data)

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
        path=str(dest),
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
    if row is None or not Path(row.path).exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found")
    return FileResponse(row.path, media_type=row.mime_type)
