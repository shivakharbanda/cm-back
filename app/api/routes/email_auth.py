"""Password-reset and email-verification endpoints."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.api.limiter import limiter
from app.config import settings
from app.models import User
from app.models.verification_token import TokenPurpose
from app.schemas.auth import UserResponse
from app.schemas.email_auth import EmailVerifyRequest, PasswordResetConfirm, PasswordResetRequest
from app.services.auth import auth_service
from app.services.email.outbox import enqueue
from app.services.email.renderer import first_name_from_email
from app.services.verification_token_service import (
    consume_token,
    count_active_tokens,
    create_token,
    invalidate_all_tokens,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

SUBJECTS = {
    "password_reset": "Reset your CreatorModo password",
    "registration": "Welcome to CreatorModo — verify your email",
}


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    db: DBSession,
) -> dict:
    """Request a password-reset email. Always returns 202 — never reveals whether the email exists."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user and user.is_active:
        active = await count_active_tokens(db, user_id=user.id, purpose=TokenPurpose.password_reset)
        if active < settings.password_reset_max_active_tokens:
            client_ip = request.client.host if request.client else None
            raw = await create_token(
                db, user_id=user.id, purpose=TokenPurpose.password_reset, request_ip=client_ip
            )
            reset_url = f"{settings.frontend_url}/reset-password?token={raw}"
            await enqueue(
                db,
                to=user.email,
                template_name="password_reset",
                context={
                    "user_first_name": first_name_from_email(user.email),
                    "reset_url": reset_url,
                    "expires_in_minutes": settings.password_reset_token_expire_minutes,
                },
                subject=SUBJECTS["password_reset"],
                idempotency_key=f"pwreset:{user.id}:{raw[:8]}",
            )

    return {"message": "If an account with that email exists, a reset link is on its way."}


@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def confirm_password_reset(
    request: Request,
    body: PasswordResetConfirm,
    db: DBSession,
) -> dict:
    """Consume a password-reset token and set a new password."""
    token = await consume_token(db, raw=body.token, purpose=TokenPurpose.password_reset)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already used reset link. Please request a new one.",
        )

    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found.")

    user.hashed_password = auth_service.hash_password(body.new_password)
    user.password_changed_at = datetime.now(timezone.utc)

    # Invalidate all other outstanding reset tokens for this user
    await invalidate_all_tokens(db, user_id=user.id, purpose=TokenPurpose.password_reset)

    logger.info("password_reset_completed user_id=%s", user.id)
    return {"message": "Password updated. You can now log in with your new password."}


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


@router.post("/email/verify", status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def verify_email(request: Request, body: EmailVerifyRequest, db: DBSession) -> dict:
    """Consume an email-verification token and mark the address as verified."""
    token = await consume_token(db, raw=body.token, purpose=TokenPurpose.email_verification)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link. Please request a new one.",
        )

    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found.")

    if not user.email_verified_at:
        user.email_verified_at = datetime.now(timezone.utc)

    return {"message": "Email verified."}


@router.post("/email/send-verification", status_code=status.HTTP_202_ACCEPTED)
async def send_verification_email(current_user: CurrentUser, db: DBSession) -> dict:
    """Re-send the verification email for the logged-in user."""
    if current_user.email_verified_at:
        return {"message": "Email is already verified."}

    active = await count_active_tokens(
        db, user_id=current_user.id, purpose=TokenPurpose.email_verification
    )
    if active >= settings.password_reset_max_active_tokens:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many pending verification emails. Please wait before requesting another.",
        )

    raw = await create_token(db, user_id=current_user.id, purpose=TokenPurpose.email_verification)
    verify_url = f"{settings.frontend_url}/verify-email?token={raw}"
    await enqueue(
        db,
        to=current_user.email,
        template_name="registration",
        context={
            "user_first_name": first_name_from_email(current_user.email),
            "verify_url": verify_url,
            "expires_in_hours": settings.email_verification_token_expire_hours,
        },
        subject=SUBJECTS["registration"],
        idempotency_key=f"verify-resend:{current_user.id}:{int(datetime.now(timezone.utc).timestamp())}",
    )

    return {"message": "Verification email sent."}
