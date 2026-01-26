"""Bio link model for Link-in-Bio feature."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.bio_page import BioPage
    from app.models.routing_rule import RoutingRule
    from app.models.analytics_event import AnalyticsEvent
    from app.models.analytics_aggregate import AnalyticsAggregate


class LinkType(str, enum.Enum):
    """Link type enum."""

    STANDARD = "standard"
    SMART = "smart"


class BioLink(Base, UUIDMixin, TimestampMixin):
    """Bio link model for simple links on bio page."""

    __tablename__ = "bio_links"

    bio_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bio_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    link_type: Mapped[LinkType] = mapped_column(
        Enum(LinkType, name="link_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=LinkType.STANDARD,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    visible_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    visible_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    bio_page: Mapped["BioPage"] = relationship(
        "BioPage",
        back_populates="links",
    )
    routing_rules: Mapped[list["RoutingRule"]] = relationship(
        "RoutingRule",
        back_populates="bio_link",
        cascade="all, delete-orphan",
    )
    analytics_events: Mapped[list["AnalyticsEvent"]] = relationship(
        "AnalyticsEvent",
        back_populates="bio_link",
    )
    analytics_aggregates: Mapped[list["AnalyticsAggregate"]] = relationship(
        "AnalyticsAggregate",
        back_populates="bio_link",
    )

    def is_visible(self, now: datetime | None = None) -> bool:
        """Check if the link is currently visible based on scheduling."""
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
