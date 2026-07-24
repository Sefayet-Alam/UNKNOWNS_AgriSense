"""Chat routes: SSE streaming turn + session/message management."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.runner import stream_agent_turn
from ..database import AsyncSessionLocal, get_db
from ..deps import get_current_user
from ..models import ChatMessage, ChatSession, User
from ..schemas import (
    ChatStreamRequest,
    MessageListOut,
    SessionListOut,
    serialize_message,
    serialize_session,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(
    payload: ChatStreamRequest,
    user: User = Depends(get_current_user),
):
    async def event_gen():
        # Use a dedicated session for the (potentially long) streaming turn so
        # it is independent of request-scoped dependency teardown.
        async with AsyncSessionLocal() as db:
            session = None
            if payload.session_id is not None:
                result = await db.execute(
                    select(ChatSession).where(
                        ChatSession.id == payload.session_id,
                        ChatSession.user_id == user.id,
                    )
                )
                session = result.scalar_one_or_none()
                if session is None:
                    err = {
                        "type": "error",
                        "detail": "Session not found.",
                        "session_id": payload.session_id,
                    }
                    yield f"data: {json.dumps(err)}\n\n"
                    return

            try:
                async for event in stream_agent_turn(
                    db, user, session, payload.message
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as exc:  # backstop
                sid = session.id if session is not None else (
                    payload.session_id or 0
                )
                err = {"type": "error", "detail": str(exc), "session_id": sid}
                yield f"data: {json.dumps(err)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/sessions", response_model=SessionListOut)
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count_subq = (
        select(
            ChatMessage.session_id,
            func.count(ChatMessage.id).label("cnt"),
        )
        .group_by(ChatMessage.session_id)
        .subquery()
    )
    result = await db.execute(
        select(ChatSession, func.coalesce(count_subq.c.cnt, 0))
        .outerjoin(count_subq, count_subq.c.session_id == ChatSession.id)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    results = [
        serialize_session(session, int(count))
        for session, count in result.all()
    ]
    return {"results": results}


@router.get("/sessions/{session_id}/messages", response_model=MessageListOut)
async def list_messages(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    owned = await db.execute(
        select(ChatSession.id).where(
            ChatSession.id == session_id, ChatSession.user_id == user.id
        )
    )
    if owned.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id)
    )
    messages = [serialize_message(m) for m in result.scalars().all()]
    return {"session_id": session_id, "results": messages}


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user.id
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    await db.delete(session)
    await db.commit()
    return None
