"""Service for page item operations (unified ordering)."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import BioPage, BioLink, BioCard, PageItem, ItemType, SocialLink
from app.schemas.page_item import ReorderRequest


class PageItemService:
    """Service for page item ordering operations."""

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

    async def get_ordered_items(
        self, page_id: UUID, user_id: UUID
    ) -> list[dict[str, Any]]:
        """Get all items (links + cards) in display order with full data."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        return await self._get_items_with_data(page_id)

    async def get_public_page_items(self, slug: str) -> dict[str, Any] | None:
        """Get public bio page with ordered items."""
        # Get bio page by slug
        result = await self.db.execute(
            select(BioPage).where(
                BioPage.slug == slug,
                BioPage.deleted_at.is_(None),
                BioPage.is_published == True,
            )
        )
        bio_page = result.scalar_one_or_none()

        if not bio_page:
            return None

        # Get ordered items with visibility filter
        items = await self._get_items_with_data(bio_page.id, public=True)

        # Get active social links
        social_links_result = await self.db.execute(
            select(SocialLink)
            .where(
                SocialLink.bio_page_id == bio_page.id,
                SocialLink.is_active == True,
            )
            .order_by(SocialLink.position)
        )
        social_links = [
            {
                "id": str(link.id),
                "platform": link.platform.value,
                "url": link.url,
            }
            for link in social_links_result.scalars().all()
        ]

        return {
            "slug": bio_page.slug,
            "display_name": bio_page.display_name,
            "bio_text": bio_page.bio_text,
            "profile_image_url": bio_page.profile_image_url,
            "theme_config": bio_page.theme_config,
            "seo_title": bio_page.seo_title,
            "seo_description": bio_page.seo_description,
            "og_image_url": bio_page.og_image_url,
            "items": items,
            "social_links": social_links,
        }

    async def _get_items_with_data(
        self, page_id: UUID, public: bool = False
    ) -> list[dict[str, Any]]:
        """Get page items with their associated data."""
        now = datetime.now(timezone.utc)

        # Get ordered page items
        result = await self.db.execute(
            select(PageItem)
            .where(PageItem.bio_page_id == page_id)
            .order_by(PageItem.position)
        )
        page_items = list(result.scalars().all())

        # Collect IDs by type
        link_ids = [pi.item_id for pi in page_items if pi.item_type == ItemType.LINK]
        card_ids = [pi.item_id for pi in page_items if pi.item_type == ItemType.CARD]

        # Batch fetch links
        links_map = {}
        if link_ids:
            result = await self.db.execute(
                select(BioLink).where(BioLink.id.in_(link_ids))
            )
            for link in result.scalars().all():
                links_map[link.id] = link

        # Batch fetch cards
        cards_map = {}
        if card_ids:
            result = await self.db.execute(
                select(BioCard).where(BioCard.id.in_(card_ids))
            )
            for card in result.scalars().all():
                cards_map[card.id] = card

        # Build result
        items = []
        for pi in page_items:
            if pi.item_type == ItemType.LINK:
                link = links_map.get(pi.item_id)
                if not link:
                    continue
                # Check visibility for public
                if public and not link.is_visible(now):
                    continue
                if public:
                    data = {
                        "id": str(link.id),
                        "title": link.title,
                        "url": link.url,
                        "thumbnail_url": link.thumbnail_url,
                    }
                else:
                    data = {
                        "id": str(link.id),
                        "title": link.title,
                        "url": link.url,
                        "link_type": link.link_type.value,
                        "is_active": link.is_active,
                        "visible_from": link.visible_from.isoformat() if link.visible_from else None,
                        "visible_until": link.visible_until.isoformat() if link.visible_until else None,
                        "thumbnail_url": link.thumbnail_url,
                    }
            else:
                card = cards_map.get(pi.item_id)
                if not card:
                    continue
                # Check visibility for public
                if public and not card.is_visible(now):
                    continue
                if public:
                    data = {
                        "id": str(card.id),
                        "badge_text": card.badge_text,
                        "headline": card.headline,
                        "description": card.description,
                        "background_color": card.background_color,
                        "background_image_url": card.background_image_url,
                        "cta_text": card.cta_text,
                        "requires_email": card.requires_email,
                    }
                else:
                    data = {
                        "id": str(card.id),
                        "badge_text": card.badge_text,
                        "headline": card.headline,
                        "description": card.description,
                        "background_color": card.background_color,
                        "background_image_url": card.background_image_url,
                        "cta_text": card.cta_text,
                        "destination_url": card.destination_url,
                        "success_message": card.success_message,
                        "requires_email": card.requires_email,
                        "is_active": card.is_active,
                        "visible_from": card.visible_from.isoformat() if card.visible_from else None,
                        "visible_until": card.visible_until.isoformat() if card.visible_until else None,
                    }

            items.append({
                "type": pi.item_type.value,
                "item_id": str(pi.item_id),
                "position": pi.position,
                "data": data,
            })

        return items

    async def reorder(
        self, page_id: UUID, request: ReorderRequest, user_id: UUID
    ) -> bool:
        """Update positions based on array order."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        # Get all page items for this page
        result = await self.db.execute(
            select(PageItem).where(PageItem.bio_page_id == page_id)
        )
        existing_items = {
            (pi.item_type, pi.item_id): pi
            for pi in result.scalars().all()
        }

        # Validate all items exist and belong to this page
        for idx, item in enumerate(request.items):
            key = (item.type, item.item_id)
            if key not in existing_items:
                raise ValueError(
                    f"Item {item.item_id} of type {item.type} not found on this page"
                )

        # Update positions
        for idx, item in enumerate(request.items):
            key = (item.type, item.item_id)
            page_item = existing_items[key]
            page_item.position = idx

        await self.db.flush()
        return True
