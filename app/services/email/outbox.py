"""Outbox enqueue helper — called from API routes inside the request DB transaction."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_outbox import EmailOutbox, OutboxStatus


async def enqueue(
    session: AsyncSession,
    *,
    to: str,
    template_name: str,
    context: dict,
    subject: str,
    idempotency_key: str | None = None,
) -> EmailOutbox | None:
    """Insert a pending outbox row. Returns None if idempotency_key already exists."""
    if idempotency_key:
        result = await session.execute(
            select(EmailOutbox).where(EmailOutbox.idempotency_key == idempotency_key)
        )
        if result.scalar_one_or_none():
            return None

    row = EmailOutbox(
        id=uuid.uuid4(),
        to_address=to,
        template_name=template_name,
        context_json=context,
        subject=subject,
        status=OutboxStatus.pending,
        next_attempt_at=datetime.now(timezone.utc),
        idempotency_key=idempotency_key,
    )
    session.add(row)
    return row
