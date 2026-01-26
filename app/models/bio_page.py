"""Bio page model for Link-in-Bio feature."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.instagram_account import InstagramAccount
    from app.models.bio_link import BioLink
    from app.models.bio_card import BioCard
    from app.models.page_item import PageItem
    from app.models.lead import Lead
    from app.models.analytics_event import AnalyticsEvent
    from app.models.analytics_aggregate import AnalyticsAggregate
    from app.models.social_link import SocialLink


# Reserved slugs that cannot be used
RESERVED_SLUGS = {
    "admin", "settings", "api", "login", "logout", "signup", "register",
    "dashboard", "app", "static", "assets", "public", "health", "status",
    "docs", "help", "support", "about", "terms", "privacy", "null", "undefined"
}


class BioPage(Base, UUIDMixin, TimestampMixin):
    """Bio page model - one per user."""

    __tablename__ = "bio_pages"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    instagram_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instagram_accounts.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    slug: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bio_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    theme_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seo_title: Mapped[str | None] = mapped_column(String(70), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(160), nullable=True)
    og_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="bio_page",
    )
    instagram_account: Mapped["InstagramAccount | None"] = relationship(
        "InstagramAccount",
        back_populates="bio_page",
    )
    links: Mapped[list["BioLink"]] = relationship(
        "BioLink",
        back_populates="bio_page",
        cascade="all, delete-orphan",
    )
    cards: Mapped[list["BioCard"]] = relationship(
        "BioCard",
        back_populates="bio_page",
        cascade="all, delete-orphan",
    )
    page_items: Mapped[list["PageItem"]] = relationship(
        "PageItem",
        back_populates="bio_page",
        cascade="all, delete-orphan",
    )
    leads: Mapped[list["Lead"]] = relationship(
        "Lead",
        back_populates="bio_page",
        cascade="all, delete-orphan",
    )
    analytics_events: Mapped[list["AnalyticsEvent"]] = relationship(
        "AnalyticsEvent",
        back_populates="bio_page",
        cascade="all, delete-orphan",
    )
    analytics_aggregates: Mapped[list["AnalyticsAggregate"]] = relationship(
        "AnalyticsAggregate",
        back_populates="bio_page",
        cascade="all, delete-orphan",
    )
    social_links: Mapped[list["SocialLink"]] = relationship(
        "SocialLink",
        back_populates="bio_page",
        cascade="all, delete-orphan",
    )

    @property
    def is_deleted(self) -> bool:
        """Check if the page is soft-deleted."""
        return self.deleted_at is not None
