"""Authentication routes: register, login, refresh (rotation), logout, me."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import bearer_scheme, get_current_user
from ..models import TokenBlacklist, User
from ..schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from ..security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _blacklist_jti(db: AsyncSession, jti: str, exp: int | datetime) -> None:
    if not jti:
        return
    existing = await db.execute(
        select(TokenBlacklist.id).where(TokenBlacklist.jti == jti)
    )
    if existing.scalar_one_or_none() is not None:
        return
    if isinstance(exp, (int, float)):
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    else:
        expires_at = exp
    db.add(TokenBlacklist(jti=jti, expires_at=expires_at))
    await db.commit()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if payload.password1 != payload.password2:
        raise HTTPException(status_code=400, detail="Passwords do not match.")
    if len(payload.password1) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters."
        )

    dup = await db.execute(
        select(User).where(
            or_(User.username == payload.username, User.email == payload.email)
        )
    )
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=400, detail="Username or email already taken."
        )

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password1),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut(id=user.id, username=user.username, email=user.email)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    access, _, _ = create_access_token(user.id)
    refresh, _, _ = create_refresh_token(user.id)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    unauthorized = HTTPException(status_code=401, detail="Invalid refresh token.")
    try:
        claims = decode_token(payload.refresh_token)
    except TokenError:
        raise unauthorized

    if claims.get("type") != "refresh":
        raise unauthorized

    jti = claims.get("jti")
    if not jti:
        raise unauthorized

    # Reuse detection: already blacklisted => reject.
    already = await db.execute(
        select(TokenBlacklist.id).where(TokenBlacklist.jti == jti)
    )
    if already.scalar_one_or_none() is not None:
        raise unauthorized

    sub = claims.get("sub")
    if sub is None:
        raise unauthorized
    user = (
        await db.execute(select(User).where(User.id == int(sub)))
    ).scalar_one_or_none()
    if user is None:
        raise unauthorized

    # Rotate: blacklist the old refresh jti, mint a fresh pair.
    await _blacklist_jti(db, jti, claims.get("exp"))
    access, _, _ = create_access_token(user.id)
    new_refresh, _, _ = create_refresh_token(user.id)
    return TokenPair(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    # Blacklist the current access token jti (get_current_user already
    # validated it, so decoding here cannot fail).
    try:
        access_claims = decode_token(credentials.credentials)
        await _blacklist_jti(
            db, access_claims.get("jti"), access_claims.get("exp")
        )
    except TokenError:
        pass

    # Blacklist the provided refresh token jti.
    try:
        refresh_claims = decode_token(payload.refresh_token)
        if refresh_claims.get("type") == "refresh":
            await _blacklist_jti(
                db, refresh_claims.get("jti"), refresh_claims.get("exp")
            )
    except TokenError:
        pass  # ignore invalid refresh token on logout

    return None


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, username=user.username, email=user.email)
