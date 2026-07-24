"""Authentication routes: register, login, refresh (rotation), logout, me."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import bearer_scheme, get_current_user
from ..config import settings
from ..models import OtpChallenge, TokenBlacklist, User
from ..schemas import (
    ActionOut,
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetStartOut,
    PasswordResetStartRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
    user_out,
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

    # payload.phone is already normalized to 01XXXXXXXXX by the schema validator.
    dup = await db.execute(select(User).where(User.phone == payload.phone))
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=400, detail="This mobile number is already registered."
        )

    user = User(
        username=payload.username,
        phone=payload.phone,
        hashed_password=hash_password(payload.password1),
        division_name=payload.division_name,
        division_code=payload.division_code,
        district_name=payload.district_name,
        district_code=payload.district_code,
        upazila_name=payload.upazila_name,
        upazila_code=payload.upazila_code,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user_out(user)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    # payload.phone is normalized to 01XXXXXXXXX by the schema validator.
    result = await db.execute(select(User).where(User.phone == payload.phone))
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
    return user_out(user)


@router.post("/password/change", response_model=ActionOut)
async def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if verify_password(payload.new_password, user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the current password.",
        )
    user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return ActionOut(message="Password updated successfully.")


@router.post("/password/reset/request", response_model=PasswordResetStartOut)
async def request_password_reset(
    payload: PasswordResetStartRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a short-lived reset challenge without revealing account existence."""
    user = (
        await db.execute(select(User).where(User.phone == payload.phone))
    ).scalar_one_or_none()
    challenge_id = str(uuid4())
    if user is not None:
        db.add(
            OtpChallenge(
                id=challenge_id,
                user_id=user.id,
                purpose="password_reset",
                provider="mock",
                provider_reference=f"mock-reset-{uuid4()}",
                otp_hash=hash_password(settings.MOCK_OTP_CODE),
                details={"phone": user.phone},
                attempts=0,
                expires_at=datetime.now(timezone.utc)
                + timedelta(seconds=settings.OTP_TTL_SECONDS),
            )
        )
        await db.commit()

    return PasswordResetStartOut(
        challenge_id=challenge_id,
        expires_in_seconds=settings.OTP_TTL_SECONDS,
        message="If the number is registered, a reset code has been prepared.",
        demo_otp=settings.MOCK_OTP_CODE,
    )


@router.post("/password/reset/confirm", response_model=ActionOut)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OtpChallenge).where(
            OtpChallenge.id == payload.challenge_id,
            OtpChallenge.purpose == "password_reset",
        )
    )
    challenge = result.scalar_one_or_none()
    invalid = HTTPException(
        status_code=400, detail="Invalid or expired reset code."
    )
    now = datetime.now(timezone.utc)
    if (
        challenge is None
        or challenge.user_id is None
        or challenge.verified_at is not None
        or challenge.expires_at <= now
    ):
        raise invalid
    if challenge.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429, detail="Too many attempts. Request a new code."
        )

    challenge.attempts += 1
    if not verify_password(payload.otp, challenge.otp_hash):
        await db.commit()
        raise invalid

    user = (
        await db.execute(select(User).where(User.id == challenge.user_id))
    ).scalar_one_or_none()
    if user is None:
        await db.commit()
        raise invalid
    user.hashed_password = hash_password(payload.new_password)
    challenge.verified_at = now
    await db.commit()
    return ActionOut(message="Password reset successfully. You can now sign in.")
