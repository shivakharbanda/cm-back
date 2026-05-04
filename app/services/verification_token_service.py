"""Verification token service — issues and consumes one-time tokens for
password-reset and email-verification flows."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.verification_token import TokenPurpose, VerificationToken


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def create_token(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    purpose: TokenPurpose,
    request_ip: str | None = None,
) -> str:
    """Create a new verification token. Returns the raw (unhashed) token string."""
    if purpose == TokenPurpose.password_reset:
        expire_delta = timedelta(minutes=settings.password_reset_token_expire_minutes)
    else:
        expire_delta = timedelta(hours=settings.email_verification_token_expire_hours)

    raw = secrets.token_urlsafe(32)
    token = VerificationToken(
        user_id=user_id,
        purpose=purpose,
        secret_hash=_hash(raw),
        expires_at=datetime.now(timezone.utc) + expire_delta,
        request_ip=request_ip,
    )
    session.add(token)
    await session.flush()
    return raw


async def consume_token(
    session: AsyncSession,
    *,
    raw: str,
    purpose: TokenPurpose,
) -> VerificationToken | None:
    """Validate and consume a token. Returns the token row on success, None on any failure."""
    h = _hash(raw)
    result = await session.execute(
        select(VerificationToken).where(
            VerificationToken.secret_hash == h,
            VerificationToken.purpose == purpose,
            VerificationToken.consumed_at.is_(None),
            VerificationToken.expires_at > datetime.now(timezone.utc),
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        return None
    token.consumed_at = datetime.now(timezone.utc)
    await session.flush()
    return token


async def invalidate_all_tokens(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    purpose: TokenPurpose,
) -> None:
    """Mark all unconsumed tokens for a user+purpose as consumed (used after password reset)."""
    result = await session.execute(
        select(VerificationToken).where(
            VerificationToken.user_id == user_id,
            VerificationToken.purpose == purpose,
            VerificationToken.consumed_at.is_(None),
        )
    )
    now = datetime.now(timezone.utc)
    for token in result.scalars().all():
        token.consumed_at = now


async def count_active_tokens(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    purpose: TokenPurpose,
) -> int:
    """Count unconsumed, non-expired tokens for a user+purpose (used for rate limiting)."""
    result = await session.execute(
        select(func.count()).where(
            VerificationToken.user_id == user_id,
            VerificationToken.purpose == purpose,
            VerificationToken.consumed_at.is_(None),
            VerificationToken.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one()
