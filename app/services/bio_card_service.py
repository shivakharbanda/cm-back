"""Service for bio card operations."""

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BioCard, BioPage, PageItem, ItemType
from app.schemas.bio_card import BioCardCreate, BioCardUpdate


class BioCardService:
    """Service for bio card CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_bio_page(self, page_id: UUID, user_id: UUID) -> BioPage | None:
        """Get bio page if it belongs to user."""
        result = await self.db.execute(
            select(BioPage).where(
                BioPage.id == page_id,
                BioPage.user_id == user_id,
                BioPage.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _get_next_position(self, page_id: UUID) -> int:
        """Get the next available position for a page item."""
        result = await self.db.execute(
            select(func.coalesce(func.max(PageItem.position), -1) + 1).where(
                PageItem.bio_page_id == page_id
            )
        )
        return result.scalar() or 0

    async def create(
        self, page_id: UUID, data: BioCardCreate, user_id: UUID
    ) -> tuple[BioCard, int]:
        """Create a new bio card and page item entry."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        # Get next position
        position = await self._get_next_position(page_id)

        # Create card
        card = BioCard(
            bio_page_id=page_id,
            badge_text=data.badge_text,
            headline=data.headline,
            description=data.description,
            background_color=data.background_color,
            background_image_url=data.background_image_url,
            cta_text=data.cta_text,
            destination_url=data.destination_url,
            success_message=data.success_message,
            requires_email=data.requires_email,
            is_active=data.is_active,
            visible_from=data.visible_from,
            visible_until=data.visible_until,
        )
        self.db.add(card)
        await self.db.flush()

        # Create page_item entry
        page_item = PageItem(
            bio_page_id=page_id,
            item_type=ItemType.CARD,
            item_id=card.id,
            position=position,
        )
        self.db.add(page_item)
        await self.db.flush()
        await self.db.refresh(card)

        return card, position

    async def get_by_id(self, card_id: UUID, user_id: UUID) -> BioCard | None:
        """Get a bio card by ID if it belongs to user."""
        result = await self.db.execute(
            select(BioCard)
            .join(BioPage)
            .where(
                BioCard.id == card_id,
                BioPage.user_id == user_id,
                BioPage.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_public(self, card_id: UUID) -> BioCard | None:
        """Get a bio card by ID for public access."""
        result = await self.db.execute(
            select(BioCard)
            .join(BioPage)
            .where(
                BioCard.id == card_id,
                BioPage.deleted_at.is_(None),
                BioPage.is_published == True,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_page(self, page_id: UUID, user_id: UUID) -> list[BioCard]:
        """List all cards for a bio page."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        result = await self.db.execute(
            select(BioCard).where(BioCard.bio_page_id == page_id)
        )
        return list(result.scalars().all())

    async def update(
        self, card_id: UUID, data: BioCardUpdate, user_id: UUID
    ) -> BioCard | None:
        """Update a bio card."""
        card = await self.get_by_id(card_id, user_id)
        if not card:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(card, field, value)

        await self.db.flush()
        await self.db.refresh(card)

        return card

    async def delete(self, card_id: UUID, user_id: UUID) -> bool:
        """Delete a bio card and its page item entry."""
        card = await self.get_by_id(card_id, user_id)
        if not card:
            return False

        page_id = card.bio_page_id

        # Delete corresponding page_item
        result = await self.db.execute(
            select(PageItem).where(
                PageItem.bio_page_id == page_id,
                PageItem.item_type == ItemType.CARD,
                PageItem.item_id == card_id,
            )
        )
        page_item = result.scalar_one_or_none()
        if page_item:
            await self.db.delete(page_item)

        # Delete card
        await self.db.delete(card)
        await self.db.flush()

        # Recompact positions
        await self._recompact_positions(page_id)

        return True

    async def _recompact_positions(self, page_id: UUID) -> None:
        """Recompact positions after deletion to remove gaps."""
        result = await self.db.execute(
            select(PageItem)
            .where(PageItem.bio_page_id == page_id)
            .order_by(PageItem.position)
        )
        items = list(result.scalars().all())

        for idx, item in enumerate(items):
            if item.position != idx:
                item.position = idx

        await self.db.flush()
