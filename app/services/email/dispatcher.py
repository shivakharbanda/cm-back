"""Email dispatcher — polls email_outbox and sends via Resend. Runs inside app.worker."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session_maker
from app.models.email_outbox import EmailOutbox, OutboxStatus
from app.services.email.renderer import render
from app.services.email.sender import send_email

logger = logging.getLogger(__name__)


def _backoff_seconds(attempts: int) -> int:
    return min(60 * (2**attempts), 3600)


async def _process_row(row: EmailOutbox, session: AsyncSession, sem: asyncio.Semaphore) -> None:
    async with sem:
        row.status = OutboxStatus.sending
        row.attempts += 1
        await session.flush()

        try:
            html, text = render(row.template_name, row.context_json)
            message_id = await send_email(
                to=row.to_address,
                subject=row.subject,
                html=html,
                text=text,
                idempotency_key=row.idempotency_key,
            )
            row.status = OutboxStatus.sent
            row.sent_at = datetime.now(timezone.utc)
            row.provider_message_id = message_id
            row.last_error = None
            logger.info("email_sent id=%s to=%s template=%s", row.id, row.to_address, row.template_name)

        except Exception as exc:
            error_str = str(exc)
            row.last_error = error_str[:2000]

            # Non-retryable: bad payload or auth failure
            exc_type = type(exc).__name__
            if any(t in exc_type for t in ("ValidationError", "AuthenticationError")):
                row.status = OutboxStatus.failed
                logger.error(
                    "email_permanent_failure id=%s type=%s error=%s",
                    row.id, exc_type, error_str,
                )
            elif row.attempts >= row.max_attempts:
                row.status = OutboxStatus.failed
                logger.error(
                    "email_max_retries_exceeded id=%s attempts=%d error=%s",
                    row.id, row.attempts, error_str,
                )
            else:
                row.status = OutboxStatus.pending
                row.next_attempt_at = datetime.now(timezone.utc) + timedelta(
                    seconds=_backoff_seconds(row.attempts)
                )
                logger.warning(
                    "email_retry_scheduled id=%s attempt=%d next=%s error=%s",
                    row.id, row.attempts, row.next_attempt_at.isoformat(), error_str,
                )


class EmailDispatcher:
    def __init__(self, shutdown_event: asyncio.Event | None = None) -> None:
        self._shutdown = shutdown_event or asyncio.Event()

    async def run(self) -> None:
        logger.info("EmailDispatcher started (interval=%ds)", settings.email_dispatch_interval_seconds)
        sem = asyncio.Semaphore(settings.email_dispatch_concurrency)

        while not self._shutdown.is_set():
            try:
                await self._dispatch_batch(sem)
            except Exception:
                logger.exception("EmailDispatcher batch error")

            try:
                await asyncio.wait_for(
                    asyncio.shield(self._shutdown.wait()),
                    timeout=settings.email_dispatch_interval_seconds,
                )
                break  # shutdown was set
            except asyncio.TimeoutError:
                pass  # normal — keep looping

        logger.info("EmailDispatcher stopped")

    async def _dispatch_batch(self, sem: asyncio.Semaphore) -> None:
        async with async_session_maker() as session:
            async with session.begin():
                result = await session.execute(
                    select(EmailOutbox)
                    .where(
                        EmailOutbox.status == OutboxStatus.pending,
                        EmailOutbox.next_attempt_at <= datetime.now(timezone.utc),
                    )
                    .order_by(EmailOutbox.next_attempt_at)
                    .limit(settings.email_dispatch_batch_size)
                    .with_for_update(skip_locked=True)
                )
                rows = result.scalars().all()

                if not rows:
                    return

                tasks = [_process_row(row, session, sem) for row in rows]
                await asyncio.gather(*tasks, return_exceptions=True)
