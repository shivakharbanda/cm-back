"""Pydantic schemas for analytics."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ViewRequest(BaseModel):
    """Schema for page view tracking request."""

    referrer: str | None = None
    user_agent: str | None = None


class ClickRequest(BaseModel):
    """Schema for link click tracking request."""

    user_agent: str | None = None


class ClickResponse(BaseModel):
    """Schema for link click response with redirect URL."""

    redirect_url: str


class AnalyticsDatePoint(BaseModel):
    """Schema for a single date point in analytics."""

    date: date
    value: int


class PageAnalyticsResponse(BaseModel):
    """Schema for page analytics response."""

    total_views: int
    total_clicks: int
    ctr: float
    views_by_date: list[AnalyticsDatePoint]
    clicks_by_date: list[AnalyticsDatePoint]


class LinkAnalyticsItem(BaseModel):
    """Schema for per-link analytics."""

    id: UUID
    title: str
    clicks: int
    ctr: float


class CardAnalyticsItem(BaseModel):
    """Schema for per-card analytics."""

    id: UUID
    headline: str
    views: int
    submissions: int
    conversion_rate: float


class ItemAnalyticsResponse(BaseModel):
    """Schema for per-item analytics response."""

    links: list[LinkAnalyticsItem]
    cards: list[CardAnalyticsItem]


class AnalyticsAggregateResponse(BaseModel):
    """Schema for analytics aggregate response."""

    id: UUID
    bio_page_id: UUID
    bio_link_id: UUID | None
    bio_card_id: UUID | None
    aggregate_type: str
    period_start: datetime
    page_views: int
    link_clicks: int
    card_views: int
    card_submits: int
    unique_visitors: int
    breakdown_data: dict[str, Any] | None

    model_config = {"from_attributes": True}
