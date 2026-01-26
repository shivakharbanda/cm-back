"""Bio card model for Link-in-Bio feature."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.bio_page import BioPage
    from app.models.lead import Lead
    from app.models.analytics_event import AnalyticsEvent
    from app.models.analytics_aggregate import AnalyticsAggregate


class BioCard(Base, UUIDMixin, TimestampMixin):
    """Bio card model for rich visual lead magnets."""

    __tablename__ = "bio_cards"

    bio_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bio_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    badge_text: Mapped[str | None] = mapped_column(String(30), nullable=True)
    headline: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    background_color: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        default="#000000",
    )
    background_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cta_text: Mapped[str] = mapped_column(String(50), nullable=False)
    destination_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    success_message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requires_email: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    visible_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    visible_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    bio_page: Mapped["BioPage"] = relationship(
        "BioPage",
        back_populates="cards",
    )
    leads: Mapped[list["Lead"]] = relationship(
        "Lead",
        back_populates="bio_card",
    )
    analytics_events: Mapped[list["AnalyticsEvent"]] = relationship(
        "AnalyticsEvent",
        back_populates="bio_card",
    )
    analytics_aggregates: Mapped[list["AnalyticsAggregate"]] = relationship(
        "AnalyticsAggregate",
        back_populates="bio_card",
    )

    def is_visible(self, now: datetime | None = None) -> bool:
        """Check if the card is currently visible based on scheduling."""
        if not self.is_active:
            return False
        if now is None:
            from datetime import timezone
            now = datetime.now(timezone.utc)
        if self.visible_from and now < self.visible_from:
            return False
        if self.visible_until and now > self.visible_until:
            return False
        return True
