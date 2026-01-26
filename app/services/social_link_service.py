"""Service for social link operations."""

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BioPage
from app.models.social_link import SocialLink, SocialPlatform
from app.schemas.social_link import SocialLinkCreate, SocialLinkUpdate, SocialLinkReorderRequest


class SocialLinkService:
    """Service for social link CRUD operations."""

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
        """Get the next available position for a social link."""
        result = await self.db.execute(
            select(func.coalesce(func.max(SocialLink.position), -1) + 1).where(
                SocialLink.bio_page_id == page_id
            )
        )
        return result.scalar() or 0

    async def create(
        self, page_id: UUID, data: SocialLinkCreate, user_id: UUID
    ) -> SocialLink:
        """Create a new social link."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        # Get next position
        position = await self._get_next_position(page_id)

        # Create social link
        social_link = SocialLink(
            bio_page_id=page_id,
            platform=data.platform,
            url=data.url,
            position=position,
            is_active=True,
        )
        self.db.add(social_link)

        try:
            await self.db.flush()
            await self.db.refresh(social_link)
        except IntegrityError:
            await self.db.rollback()
            raise ValueError(f"A {data.platform.value} link already exists for this page")

        return social_link

    async def get_by_id(
        self, social_link_id: UUID, user_id: UUID
    ) -> SocialLink | None:
        """Get a social link by ID if it belongs to user."""
        result = await self.db.execute(
            select(SocialLink)
            .join(BioPage)
            .where(
                SocialLink.id == social_link_id,
                BioPage.user_id == user_id,
                BioPage.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_page(self, page_id: UUID, user_id: UUID) -> list[SocialLink]:
        """List all social links for a bio page."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        result = await self.db.execute(
            select(SocialLink)
            .where(SocialLink.bio_page_id == page_id)
            .order_by(SocialLink.position)
        )
        return list(result.scalars().all())

    async def list_public_for_page(self, page_id: UUID) -> list[SocialLink]:
        """List all active social links for a public bio page."""
        result = await self.db.execute(
            select(SocialLink)
            .where(
                SocialLink.bio_page_id == page_id,
                SocialLink.is_active == True,
            )
            .order_by(SocialLink.position)
        )
        return list(result.scalars().all())

    async def update(
        self, social_link_id: UUID, data: SocialLinkUpdate, user_id: UUID
    ) -> SocialLink | None:
        """Update a social link."""
        social_link = await self.get_by_id(social_link_id, user_id)
        if not social_link:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(social_link, field, value)

        await self.db.flush()
        await self.db.refresh(social_link)

        return social_link

    async def delete(self, social_link_id: UUID, user_id: UUID) -> bool:
        """Delete a social link."""
        social_link = await self.get_by_id(social_link_id, user_id)
        if not social_link:
            return False

        page_id = social_link.bio_page_id

        # Delete social link
        await self.db.delete(social_link)
        await self.db.flush()

        # Recompact positions
        await self._recompact_positions(page_id)

        return True

    async def reorder(
        self, page_id: UUID, request: SocialLinkReorderRequest, user_id: UUID
    ) -> bool:
        """Reorder social links based on provided positions."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        # Get all social links for this page
        result = await self.db.execute(
            select(SocialLink).where(SocialLink.bio_page_id == page_id)
        )
        existing_links = {link.id: link for link in result.scalars().all()}

        # Validate all items exist and belong to this page
        for item in request.items:
            if item.id not in existing_links:
                raise ValueError(f"Social link {item.id} not found on this page")

        # Update positions
        for item in request.items:
            existing_links[item.id].position = item.position

        await self.db.flush()
        return True

    async def _recompact_positions(self, page_id: UUID) -> None:
        """Recompact positions after deletion to remove gaps."""
        result = await self.db.execute(
            select(SocialLink)
            .where(SocialLink.bio_page_id == page_id)
            .order_by(SocialLink.position)
        )
        links = list(result.scalars().all())

        for idx, link in enumerate(links):
            if link.position != idx:
                link.position = idx

        await self.db.flush()
