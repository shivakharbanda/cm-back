"""Service for analytics tracking and querying."""

import csv
import io
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalyticsEvent, AnalyticsAggregate, EventType, AggregateType,
    BioPage, BioLink, BioCard,
)


class AnalyticsService:
    """Service for analytics tracking and querying."""

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

    async def track_page_view(
        self, page_id: UUID, visitor_data: dict[str, Any] | None = None
    ) -> None:
        """Track a page view event."""
        event = AnalyticsEvent(
            bio_page_id=page_id,
            event_type=EventType.PAGE_VIEW,
            occurred_at=datetime.now(timezone.utc),
            visitor_data=visitor_data,
        )
        self.db.add(event)
        await self.db.flush()

    async def track_link_click(
        self, page_id: UUID, link_id: UUID, visitor_data: dict[str, Any] | None = None
    ) -> None:
        """Track a link click event."""
        event = AnalyticsEvent(
            bio_page_id=page_id,
            bio_link_id=link_id,
            event_type=EventType.LINK_CLICK,
            occurred_at=datetime.now(timezone.utc),
            visitor_data=visitor_data,
        )
        self.db.add(event)
        await self.db.flush()

    async def track_card_view(
        self, page_id: UUID, card_id: UUID, visitor_data: dict[str, Any] | None = None
    ) -> None:
        """Track a card view event."""
        event = AnalyticsEvent(
            bio_page_id=page_id,
            bio_card_id=card_id,
            event_type=EventType.CARD_VIEW,
            occurred_at=datetime.now(timezone.utc),
            visitor_data=visitor_data,
        )
        self.db.add(event)
        await self.db.flush()

    async def track_card_submission(
        self, page_id: UUID, card_id: UUID
    ) -> None:
        """Track a card submission event."""
        event = AnalyticsEvent(
            bio_page_id=page_id,
            bio_card_id=card_id,
            event_type=EventType.CARD_SUBMIT,
            occurred_at=datetime.now(timezone.utc),
        )
        self.db.add(event)
        await self.db.flush()

    async def get_page_analytics(
        self,
        page_id: UUID,
        user_id: UUID,
        start_date: date,
        end_date: date,
        granularity: str = "daily",
    ) -> dict[str, Any]:
        """Get page analytics for a date range."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        # Get total views
        result = await self.db.execute(
            select(func.count(AnalyticsEvent.id)).where(
                AnalyticsEvent.bio_page_id == page_id,
                AnalyticsEvent.event_type == EventType.PAGE_VIEW,
                AnalyticsEvent.occurred_at >= start_dt,
                AnalyticsEvent.occurred_at <= end_dt,
            )
        )
        total_views = result.scalar() or 0

        # Get total clicks
        result = await self.db.execute(
            select(func.count(AnalyticsEvent.id)).where(
                AnalyticsEvent.bio_page_id == page_id,
                AnalyticsEvent.event_type == EventType.LINK_CLICK,
                AnalyticsEvent.occurred_at >= start_dt,
                AnalyticsEvent.occurred_at <= end_dt,
            )
        )
        total_clicks = result.scalar() or 0

        # Calculate CTR
        ctr = (total_clicks / total_views * 100) if total_views > 0 else 0

        # Get views by date
        views_by_date = await self._get_events_by_date(
            page_id, EventType.PAGE_VIEW, start_dt, end_dt
        )

        # Get clicks by date
        clicks_by_date = await self._get_events_by_date(
            page_id, EventType.LINK_CLICK, start_dt, end_dt
        )

        return {
            "total_views": total_views,
            "total_clicks": total_clicks,
            "ctr": round(ctr, 2),
            "views_by_date": views_by_date,
            "clicks_by_date": clicks_by_date,
        }

    async def _get_events_by_date(
        self,
        page_id: UUID,
        event_type: EventType,
        start_dt: datetime,
        end_dt: datetime,
    ) -> list[dict[str, Any]]:
        """Get event counts grouped by date."""
        result = await self.db.execute(
            select(
                func.date(AnalyticsEvent.occurred_at).label("date"),
                func.count(AnalyticsEvent.id).label("count"),
            )
            .where(
                AnalyticsEvent.bio_page_id == page_id,
                AnalyticsEvent.event_type == event_type,
                AnalyticsEvent.occurred_at >= start_dt,
                AnalyticsEvent.occurred_at <= end_dt,
            )
            .group_by(func.date(AnalyticsEvent.occurred_at))
            .order_by(func.date(AnalyticsEvent.occurred_at))
        )

        return [
            {"date": str(row.date), "value": row.count}
            for row in result.all()
        ]

    async def get_item_analytics(
        self,
        page_id: UUID,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Get per-item (links and cards) analytics."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        # Get total page views for CTR calculation
        result = await self.db.execute(
            select(func.count(AnalyticsEvent.id)).where(
                AnalyticsEvent.bio_page_id == page_id,
                AnalyticsEvent.event_type == EventType.PAGE_VIEW,
                AnalyticsEvent.occurred_at >= start_dt,
                AnalyticsEvent.occurred_at <= end_dt,
            )
        )
        total_views = result.scalar() or 0

        # Get link analytics
        links = await self._get_link_analytics(page_id, start_dt, end_dt, total_views)

        # Get card analytics
        cards = await self._get_card_analytics(page_id, start_dt, end_dt)

        return {
            "links": links,
            "cards": cards,
        }

    async def _get_link_analytics(
        self,
        page_id: UUID,
        start_dt: datetime,
        end_dt: datetime,
        total_views: int,
    ) -> list[dict[str, Any]]:
        """Get analytics for all links."""
        # Get all links for this page
        result = await self.db.execute(
            select(BioLink).where(BioLink.bio_page_id == page_id)
        )
        links = list(result.scalars().all())

        # Get click counts per link
        result = await self.db.execute(
            select(
                AnalyticsEvent.bio_link_id,
                func.count(AnalyticsEvent.id).label("clicks"),
            )
            .where(
                AnalyticsEvent.bio_page_id == page_id,
                AnalyticsEvent.event_type == EventType.LINK_CLICK,
                AnalyticsEvent.bio_link_id.is_not(None),
                AnalyticsEvent.occurred_at >= start_dt,
                AnalyticsEvent.occurred_at <= end_dt,
            )
            .group_by(AnalyticsEvent.bio_link_id)
        )
        clicks_map = {row.bio_link_id: row.clicks for row in result.all()}

        return [
            {
                "id": str(link.id),
                "title": link.title,
                "clicks": clicks_map.get(link.id, 0),
                "ctr": round(
                    (clicks_map.get(link.id, 0) / total_views * 100) if total_views > 0 else 0,
                    2
                ),
            }
            for link in links
        ]

    async def _get_card_analytics(
        self,
        page_id: UUID,
        start_dt: datetime,
        end_dt: datetime,
    ) -> list[dict[str, Any]]:
        """Get analytics for all cards."""
        # Get all cards for this page
        result = await self.db.execute(
            select(BioCard).where(BioCard.bio_page_id == page_id)
        )
        cards = list(result.scalars().all())

        # Get view counts per card
        result = await self.db.execute(
            select(
                AnalyticsEvent.bio_card_id,
                func.count(AnalyticsEvent.id).label("views"),
            )
            .where(
                AnalyticsEvent.bio_page_id == page_id,
                AnalyticsEvent.event_type == EventType.CARD_VIEW,
                AnalyticsEvent.bio_card_id.is_not(None),
                AnalyticsEvent.occurred_at >= start_dt,
                AnalyticsEvent.occurred_at <= end_dt,
            )
            .group_by(AnalyticsEvent.bio_card_id)
        )
        views_map = {row.bio_card_id: row.views for row in result.all()}

        # Get submission counts per card
        result = await self.db.execute(
            select(
                AnalyticsEvent.bio_card_id,
                func.count(AnalyticsEvent.id).label("submissions"),
            )
            .where(
                AnalyticsEvent.bio_page_id == page_id,
                AnalyticsEvent.event_type == EventType.CARD_SUBMIT,
                AnalyticsEvent.bio_card_id.is_not(None),
                AnalyticsEvent.occurred_at >= start_dt,
                AnalyticsEvent.occurred_at <= end_dt,
            )
            .group_by(AnalyticsEvent.bio_card_id)
        )
        submissions_map = {row.bio_card_id: row.submissions for row in result.all()}

        return [
            {
                "id": str(card.id),
                "headline": card.headline,
                "views": views_map.get(card.id, 0),
                "submissions": submissions_map.get(card.id, 0),
                "conversion_rate": round(
                    (submissions_map.get(card.id, 0) / views_map.get(card.id, 0) * 100)
                    if views_map.get(card.id, 0) > 0 else 0,
                    2
                ),
            }
            for card in cards
        ]

    async def export_csv(
        self,
        page_id: UUID,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> bytes:
        """Export analytics as CSV."""
        bio_page = await self._get_bio_page(page_id, user_id)
        if not bio_page:
            raise ValueError("Bio page not found or doesn't belong to user")

        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        # Get all events
        result = await self.db.execute(
            select(AnalyticsEvent)
            .where(
                AnalyticsEvent.bio_page_id == page_id,
                AnalyticsEvent.occurred_at >= start_dt,
                AnalyticsEvent.occurred_at <= end_dt,
            )
            .order_by(AnalyticsEvent.occurred_at.desc())
        )
        events = list(result.scalars().all())

        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "event_type", "occurred_at", "link_id", "card_id", "country", "device", "referrer"
        ])

        for event in events:
            country = ""
            device = ""
            referrer = ""
            if event.visitor_data:
                country = event.visitor_data.get("country", "")
                device = event.visitor_data.get("device_type", "")
                referrer = event.visitor_data.get("referrer", "")

            writer.writerow([
                event.event_type.value,
                event.occurred_at.isoformat(),
                str(event.bio_link_id) if event.bio_link_id else "",
                str(event.bio_card_id) if event.bio_card_id else "",
                country,
                device,
                referrer,
            ])

        return output.getvalue().encode("utf-8")
