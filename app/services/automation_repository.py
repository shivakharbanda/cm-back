"""Repository for automation operations."""

from datetime import date
from uuid import UUID

from sqlalchemy import select, func, case, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Automation, InstagramAccount, DMSentLog, CommentReplyLog
from app.schemas.automation import (
    AutomationCreate,
    AutomationUpdate,
    AutomationAnalytics,
    AutomationAnalyticsSummary,
    DatePoint,
)


class AutomationRepository:
    """Repository for automation CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_instagram_account_ids(self, user_id: UUID) -> list[UUID]:
        """Get all Instagram account IDs for a user."""
        result = await self.db.execute(
            select(InstagramAccount.id).where(InstagramAccount.user_id == user_id)
        )
        return list(result.scalars().all())

    async def create(self, data: AutomationCreate, user_id: UUID) -> Automation:
        """Create a new automation."""
        # Verify the Instagram account belongs to the user
        result = await self.db.execute(
            select(InstagramAccount).where(
                InstagramAccount.id == data.instagram_account_id,
                InstagramAccount.user_id == user_id,
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            raise ValueError("Instagram account not found or doesn't belong to user")

        automation = Automation(
            instagram_account_id=data.instagram_account_id,
            name=data.name,
            post_id=data.post_id,
            trigger_type=data.trigger_type,
            keywords=data.keywords,
            dm_message_template=data.dm_message_template,
            comment_reply_enabled=data.comment_reply_enabled,
            comment_reply_template=data.comment_reply_template,
        )

        self.db.add(automation)
        await self.db.flush()
        await self.db.refresh(automation)

        return automation

    async def get_by_id(self, automation_id: UUID, user_id: UUID) -> Automation | None:
        """Get an automation by ID if it belongs to the user."""
        account_ids = await self.get_user_instagram_account_ids(user_id)

        result = await self.db.execute(
            select(Automation).where(
                Automation.id == automation_id,
                Automation.instagram_account_id.in_(account_ids),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: UUID) -> list[Automation]:
        """List all automations for a user."""
        account_ids = await self.get_user_instagram_account_ids(user_id)

        result = await self.db.execute(
            select(Automation)
            .where(Automation.instagram_account_id.in_(account_ids))
            .order_by(Automation.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_account(self, account_id: UUID, user_id: UUID) -> list[Automation]:
        """List all automations for a specific Instagram account."""
        # Verify account belongs to user
        result = await self.db.execute(
            select(InstagramAccount).where(
                InstagramAccount.id == account_id,
                InstagramAccount.user_id == user_id,
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            raise ValueError("Instagram account not found or doesn't belong to user")

        result = await self.db.execute(
            select(Automation)
            .where(Automation.instagram_account_id == account_id)
            .order_by(Automation.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(
        self, automation_id: UUID, data: AutomationUpdate, user_id: UUID
    ) -> Automation | None:
        """Update an automation."""
        automation = await self.get_by_id(automation_id, user_id)

        if not automation:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(automation, field, value)

        await self.db.flush()
        await self.db.refresh(automation)

        return automation

    async def delete(self, automation_id: UUID, user_id: UUID) -> bool:
        """Delete an automation."""
        automation = await self.get_by_id(automation_id, user_id)

        if not automation:
            return False

        await self.db.delete(automation)
        return True

    async def activate(self, automation_id: UUID, user_id: UUID) -> Automation | None:
        """Activate an automation."""
        automation = await self.get_by_id(automation_id, user_id)

        if not automation:
            return None

        automation.is_active = True
        await self.db.flush()
        await self.db.refresh(automation)

        return automation

    async def deactivate(self, automation_id: UUID, user_id: UUID) -> Automation | None:
        """Deactivate an automation."""
        automation = await self.get_by_id(automation_id, user_id)

        if not automation:
            return None

        automation.is_active = False
        await self.db.flush()
        await self.db.refresh(automation)

        return automation

    async def get_analytics(
        self,
        automation_id: UUID,
        user_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AutomationAnalytics | None:
        """Get full analytics for a specific automation."""
        # Verify automation belongs to user
        automation = await self.get_by_id(automation_id, user_id)
        if not automation:
            return None

        # Build date filter for DM logs
        dm_filters = [DMSentLog.automation_id == automation_id]
        if start_date:
            dm_filters.append(func.date(DMSentLog.sent_at) >= start_date)
        if end_date:
            dm_filters.append(func.date(DMSentLog.sent_at) <= end_date)

        # Build date filter for comment reply logs
        reply_filters = [CommentReplyLog.automation_id == automation_id]
        if start_date:
            reply_filters.append(func.date(CommentReplyLog.sent_at) >= start_date)
        if end_date:
            reply_filters.append(func.date(CommentReplyLog.sent_at) <= end_date)

        # Get DM stats
        dm_result = await self.db.execute(
            select(
                func.count(case((DMSentLog.status == "sent", 1))).label("sent"),
                func.count(case((DMSentLog.status == "failed", 1))).label("failed"),
                func.count(distinct(DMSentLog.commenter_user_id)).label("unique_users"),
            ).where(*dm_filters)
        )
        dm_row = dm_result.one()
        dms_sent = dm_row.sent or 0
        dms_failed = dm_row.failed or 0
        unique_people = dm_row.unique_users or 0

        # Get comment reply stats
        reply_result = await self.db.execute(
            select(
                func.count(case((CommentReplyLog.status == "sent", 1))).label("sent"),
                func.count(case((CommentReplyLog.status == "failed", 1))).label("failed"),
            ).where(*reply_filters)
        )
        reply_row = reply_result.one()
        replies_sent = reply_row.sent or 0
        replies_failed = reply_row.failed or 0

        # Calculate success rates
        dm_total = dms_sent + dms_failed
        dm_success_rate = (dms_sent / dm_total * 100) if dm_total > 0 else 0.0

        reply_total = replies_sent + replies_failed
        reply_success_rate = (replies_sent / reply_total * 100) if reply_total > 0 else 0.0

        # Get DMs by date
        dms_by_date_result = await self.db.execute(
            select(
                func.date(DMSentLog.sent_at).label("date"),
                func.count(case((DMSentLog.status == "sent", 1))).label("count"),
            )
            .where(*dm_filters)
            .group_by(func.date(DMSentLog.sent_at))
            .order_by(func.date(DMSentLog.sent_at))
        )
        dms_by_date = [
            DatePoint(date=str(row.date), value=row.count or 0)
            for row in dms_by_date_result
        ]

        # Get replies by date
        replies_by_date_result = await self.db.execute(
            select(
                func.date(CommentReplyLog.sent_at).label("date"),
                func.count(case((CommentReplyLog.status == "sent", 1))).label("count"),
            )
            .where(*reply_filters)
            .group_by(func.date(CommentReplyLog.sent_at))
            .order_by(func.date(CommentReplyLog.sent_at))
        )
        replies_by_date = [
            DatePoint(date=str(row.date), value=row.count or 0)
            for row in replies_by_date_result
        ]

        return AutomationAnalytics(
            automation_id=str(automation_id),
            total_dms_sent=dms_sent,
            total_dms_failed=dms_failed,
            dm_success_rate=round(dm_success_rate, 1),
            unique_people_reached=unique_people,
            total_comment_replies=replies_sent,
            total_comment_replies_failed=replies_failed,
            comment_reply_success_rate=round(reply_success_rate, 1),
            dms_by_date=dms_by_date,
            replies_by_date=replies_by_date,
        )

    async def get_all_summaries(
        self, user_id: UUID
    ) -> dict[str, AutomationAnalyticsSummary]:
        """Get summary analytics for all user's automations (for inline display)."""
        account_ids = await self.get_user_instagram_account_ids(user_id)

        if not account_ids:
            return {}

        # Get all automation IDs for this user
        automations_result = await self.db.execute(
            select(Automation.id).where(Automation.instagram_account_id.in_(account_ids))
        )
        automation_ids = [row[0] for row in automations_result]

        if not automation_ids:
            return {}

        # Get DM stats grouped by automation
        dm_result = await self.db.execute(
            select(
                DMSentLog.automation_id,
                func.count(case((DMSentLog.status == "sent", 1))).label("sent"),
                func.count(distinct(DMSentLog.commenter_user_id)).label("unique_users"),
            )
            .where(DMSentLog.automation_id.in_(automation_ids))
            .group_by(DMSentLog.automation_id)
        )

        summaries: dict[str, AutomationAnalyticsSummary] = {}
        for row in dm_result:
            summaries[str(row.automation_id)] = AutomationAnalyticsSummary(
                dms_sent=row.sent or 0,
                people_reached=row.unique_users or 0,
            )

        # Fill in automations with no DMs
        for automation_id in automation_ids:
            aid_str = str(automation_id)
            if aid_str not in summaries:
                summaries[aid_str] = AutomationAnalyticsSummary(
                    dms_sent=0,
                    people_reached=0,
                )

        return summaries

    async def get_commenters(
        self, automation_id: UUID, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> tuple[list[DMSentLog], int]:
        """Get list of people who received DMs from this automation."""
        # Verify ownership
        automation = await self.get_by_id(automation_id, user_id)
        if not automation:
            return [], 0

        # Get total count
        count_result = await self.db.execute(
            select(func.count()).where(DMSentLog.automation_id == automation_id)
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await self.db.execute(
            select(DMSentLog)
            .where(DMSentLog.automation_id == automation_id)
            .order_by(DMSentLog.sent_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total
