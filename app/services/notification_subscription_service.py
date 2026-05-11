"""Service for notification subscriptions — capture only, no email sending."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_subscription import NotificationSubscription
from app.schemas.notification_subscription import NotificationSubscriptionCreate


class NotificationSubscriptionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def subscribe(self, data: NotificationSubscriptionCreate) -> NotificationSubscription:
        """Save a subscription. Silently skips if email+type already exists."""
        existing = await self.db.execute(
            select(NotificationSubscription).where(
                NotificationSubscription.email == data.email,
                NotificationSubscription.notification_type == data.notification_type,
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            return row

        sub = NotificationSubscription(**data.model_dump())
        self.db.add(sub)
        await self.db.flush()
        await self.db.refresh(sub)
        return sub
