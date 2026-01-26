"""Analytics event model for tracking page views, clicks, etc."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.bio_page import BioPage
    from app.models.bio_link import BioLink
    from app.models.bio_card import BioCard


class EventType(str, enum.Enum):
    """Analytics event type enum."""

    PAGE_VIEW = "page_view"
    LINK_CLICK = "link_click"
    CARD_VIEW = "card_view"
    CARD_SUBMIT = "card_submit"


class AnalyticsEvent(Base, UUIDMixin):
    """Analytics event model for raw event tracking."""

    __tablename__ = "analytics_events"

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
        index=True,
    )
    bio_card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bio_cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    visitor_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    bio_page: Mapped["BioPage"] = relationship(
        "BioPage",
        back_populates="analytics_events",
    )
    bio_link: Mapped["BioLink | None"] = relationship(
        "BioLink",
        back_populates="analytics_events",
    )
    bio_card: Mapped["BioCard | None"] = relationship(
        "BioCard",
        back_populates="analytics_events",
    )
