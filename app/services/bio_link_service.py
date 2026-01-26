"""Service for bio link operations."""

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BioLink, BioPage, PageItem, ItemType
from app.schemas.bio_link import BioLinkCreate, BioLinkUpdate


class BioLinkService:
    """Service for bio link CRUD operations."""

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
        self, page_id: UUID, data: BioLinkCreate, user_id: UUID
    ) -> tuple[BioLink, int]:
        """Create a new bio link and page item entry."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        # Get next position
        position = await self._get_next_position(page_id)

        thumbnail_url = data.thumbnail_url

        # Create link
        link = BioLink(
            bio_page_id=page_id,
            title=data.title,
            url=data.url,
            link_type=data.link_type,
            position=position,
            is_active=data.is_active,
            visible_from=data.visible_from,
            visible_until=data.visible_until,
            thumbnail_url=thumbnail_url,
        )
        self.db.add(link)
        await self.db.flush()

        # Create page_item entry
        page_item = PageItem(
            bio_page_id=page_id,
            item_type=ItemType.LINK,
            item_id=link.id,
            position=position,
        )
        self.db.add(page_item)
        await self.db.flush()
        await self.db.refresh(link)

        return link, position

    async def get_by_id(
        self, link_id: UUID, user_id: UUID
    ) -> BioLink | None:
        """Get a bio link by ID if it belongs to user."""
        result = await self.db.execute(
            select(BioLink)
            .join(BioPage)
            .where(
                BioLink.id == link_id,
                BioPage.user_id == user_id,
                BioPage.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_page(self, page_id: UUID, user_id: UUID) -> list[BioLink]:
        """List all links for a bio page."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        result = await self.db.execute(
            select(BioLink)
            .where(BioLink.bio_page_id == page_id)
            .order_by(BioLink.position)
        )
        return list(result.scalars().all())

    async def update(
        self, link_id: UUID, data: BioLinkUpdate, user_id: UUID
    ) -> BioLink | None:
        """Update a bio link."""
        link = await self.get_by_id(link_id, user_id)
        if not link:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(link, field, value)

        await self.db.flush()
        await self.db.refresh(link)

        return link

    async def delete(self, link_id: UUID, user_id: UUID) -> bool:
        """Delete a bio link and its page item entry."""
        link = await self.get_by_id(link_id, user_id)
        if not link:
            return False

        page_id = link.bio_page_id

        # Delete corresponding page_item
        result = await self.db.execute(
            select(PageItem).where(
                PageItem.bio_page_id == page_id,
                PageItem.item_type == ItemType.LINK,
                PageItem.item_id == link_id,
            )
        )
        page_item = result.scalar_one_or_none()
        if page_item:
            await self.db.delete(page_item)

        # Delete link
        await self.db.delete(link)
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
