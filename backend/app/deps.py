"""Shared FastAPI dependencies: auth / current-user resolution."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import TokenBlacklist, User
from .security import TokenError, decode_token

bearer_scheme = HTTPBearer(auto_error=False)


async def _jti_blacklisted(db: AsyncSession, jti: str) -> bool:
    result = await db.execute(
        select(TokenBlacklist.id).where(TokenBlacklist.jti == jti)
    )
    return result.scalar_one_or_none() is not None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or not credentials.credentials:
        raise unauthorized

    try:
        payload = decode_token(credentials.credentials)
    except TokenError:
        raise unauthorized

    if payload.get("type") != "access":
        raise unauthorized

    jti = payload.get("jti")
    if not jti or await _jti_blacklisted(db, jti):
        raise unauthorized

    sub = payload.get("sub")
    if sub is None:
        raise unauthorized

    result = await db.execute(select(User).where(User.id == int(sub)))
    user = result.scalar_one_or_none()
    if user is None:
        raise unauthorized

    return user
