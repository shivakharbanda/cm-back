"""Analytics aggregate model for pre-computed dashboard data."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.bio_page import BioPage
    from app.models.bio_link import BioLink
    from app.models.bio_card import BioCard


class AggregateType(str, enum.Enum):
    """Aggregate type enum for time periods."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class AnalyticsAggregate(Base, UUIDMixin):
    """Analytics aggregate model for pre-computed metrics."""

    __tablename__ = "analytics_aggregates"
    __table_args__ = (
        UniqueConstraint(
            "bio_page_id", "bio_link_id", "bio_card_id", "aggregate_type", "period_start",
            name="uq_analytics_aggregates_period"
        ),
    )

    bio_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bio_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bio_link_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bio_links.id", ondelete="SET NULL"),
        nullable=True,
    )
    bio_card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bio_cards.id", ondelete="SET NULL"),
        nullable=True,
    )
    aggregate_type: Mapped[AggregateType] = mapped_column(
        Enum(AggregateType, name="aggregate_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    page_views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    link_clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    card_views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    card_submits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_visitors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    breakdown_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    bio_page: Mapped["BioPage"] = relationship(
        "BioPage",
        back_populates="analytics_aggregates",
    )
    bio_link: Mapped["BioLink | None"] = relationship(
        "BioLink",
        back_populates="analytics_aggregates",
    )
    bio_card: Mapped["BioCard | None"] = relationship(
        "BioCard",
        back_populates="analytics_aggregates",
    )
