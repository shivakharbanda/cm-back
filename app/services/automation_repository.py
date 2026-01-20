"""Repository for automation operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Automation, InstagramAccount
from app.schemas.automation import AutomationCreate, AutomationUpdate


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
