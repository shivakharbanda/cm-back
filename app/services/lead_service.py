"""Service for lead capture and management."""

import csv
import io
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead, BioPage, BioCard, SourceType


class LeadService:
    """Service for lead capture and export operations."""

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

    async def capture(
        self,
        page_id: UUID,
        card_id: UUID,
        email: str,
        metadata: dict[str, Any] | None = None,
    ) -> Lead:
        """Capture a lead from card submission."""
        # Verify card exists and belongs to a published page
        result = await self.db.execute(
            select(BioCard)
            .join(BioPage)
            .where(
                BioCard.id == card_id,
                BioCard.bio_page_id == page_id,
                BioPage.deleted_at.is_(None),
                BioPage.is_published == True,
            )
        )
        card = result.scalar_one_or_none()

        if not card:
            raise ValueError("Card not found or page not published")

        lead = Lead(
            bio_page_id=page_id,
            bio_card_id=card_id,
            email=email,
            source_type=SourceType.CARD,
            metadata=metadata,
        )
        self.db.add(lead)
        await self.db.flush()
        await self.db.refresh(lead)

        return lead

    async def list_leads(
        self,
        page_id: UUID,
        user_id: UUID,
        page: int = 1,
        limit: int = 50,
        card_id: UUID | None = None,
    ) -> tuple[list[Lead], int]:
        """List leads for a bio page with pagination."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        # Build query
        query = select(Lead).where(Lead.bio_page_id == page_id)
        count_query = select(func.count(Lead.id)).where(Lead.bio_page_id == page_id)

        if card_id:
            query = query.where(Lead.bio_card_id == card_id)
            count_query = count_query.where(Lead.bio_card_id == card_id)

        # Get total count
        result = await self.db.execute(count_query)
        total = result.scalar() or 0

        # Get paginated leads
        offset = (page - 1) * limit
        query = query.order_by(Lead.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        leads = list(result.scalars().all())

        return leads, total

    async def get_lead(self, lead_id: UUID, user_id: UUID) -> Lead | None:
        """Get a lead by ID if it belongs to user's page."""
        result = await self.db.execute(
            select(Lead)
            .join(BioPage)
            .where(
                Lead.id == lead_id,
                BioPage.user_id == user_id,
                BioPage.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def delete_lead(self, lead_id: UUID, user_id: UUID) -> bool:
        """Delete a lead."""
        lead = await self.get_lead(lead_id, user_id)
        if not lead:
            return False

        await self.db.delete(lead)
        await self.db.flush()

        return True

    async def export_csv(self, page_id: UUID, user_id: UUID) -> bytes:
        """Export leads as CSV."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        # Get all leads with card info
        result = await self.db.execute(
            select(Lead)
            .where(Lead.bio_page_id == page_id)
            .order_by(Lead.created_at.desc())
        )
        leads = list(result.scalars().all())

        # Get card headlines for mapping
        card_ids = [lead.bio_card_id for lead in leads if lead.bio_card_id]
        cards_map = {}
        if card_ids:
            result = await self.db.execute(
                select(BioCard).where(BioCard.id.in_(card_ids))
            )
            cards_map = {card.id: card.headline for card in result.scalars().all()}

        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "email", "phone", "source", "card", "country", "captured_at"
        ])

        for lead in leads:
            card_headline = cards_map.get(lead.bio_card_id, "")
            country = ""
            if lead.metadata:
                country = lead.metadata.get("country", "")

            writer.writerow([
                lead.email,
                lead.phone or "",
                lead.source_type.value,
                card_headline,
                country,
                lead.created_at.isoformat(),
            ])

        return output.getvalue().encode("utf-8")
