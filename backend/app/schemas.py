"""Pydantic request/response schemas and serialization helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    email: EmailStr
    password1: str = Field(min_length=8)
    password2: str = Field(min_length=8)


class UserOut(BaseModel):
    id: int
    username: str
    email: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
class ChatStreamRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: int | None = None


class ToolTraceEntry(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: str = ""


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    tool_trace: list[ToolTraceEntry] = Field(default_factory=list)
    model: str = ""
    created_at: datetime


class SessionOut(BaseModel):
    id: int
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class SessionListOut(BaseModel):
    results: list[SessionOut]


class MessageListOut(BaseModel):
    session_id: int
    results: list[MessageOut]


# --------------------------------------------------------------------------- #
# Serialization helpers (used for both REST bodies and SSE frames)
# --------------------------------------------------------------------------- #
def serialize_message(msg) -> dict[str, Any]:
    return {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content or "",
        "tool_trace": msg.tool_trace or [],
        "model": msg.model or "",
        "created_at": _iso(msg.created_at),
    }


def serialize_session(session, message_count: int) -> dict[str, Any]:
    return {
        "id": session.id,
        "title": session.title or "",
        "message_count": message_count,
        "created_at": _iso(session.created_at),
        "updated_at": _iso(session.updated_at),
    }


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
