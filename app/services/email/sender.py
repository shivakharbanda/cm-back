"""Resend email sender — wraps the sync SDK in asyncio.to_thread."""

import asyncio
import logging

import resend

from app.config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key

_FROM = f"{settings.resend_from_name} <{settings.resend_from_address}>"


async def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    text: str,
    idempotency_key: str | None = None,
) -> str:
    """Send a transactional email via Resend. Returns the Resend message id."""

    params: resend.Emails.SendParams = {
        "from": _FROM,
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }
    if settings.resend_reply_to:
        params["reply_to"] = settings.resend_reply_to

    def _send() -> str:
        result = resend.Emails.send(params)
        return result["id"]

    return await asyncio.to_thread(_send)
