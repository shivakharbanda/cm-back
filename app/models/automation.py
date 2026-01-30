"""Automation and DM sent log models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.instagram_account import InstagramAccount


class TriggerType(str, enum.Enum):
    """Automation trigger types."""

    ALL_COMMENTS = "all_comments"
    KEYWORD = "keyword"


class MessageType(str, enum.Enum):
    """DM message types."""

    TEXT = "text"
    CAROUSEL = "carousel"


class Automation(Base, UUIDMixin, TimestampMixin):
    """Automation configuration model."""

    __tablename__ = "automations"

    instagram_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instagram_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    post_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trigger_type: Mapped[TriggerType] = mapped_column(
        Enum(TriggerType, name="trigger_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="message_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=MessageType.TEXT,
        server_default="text",
    )
    dm_message_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    carousel_elements: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    comment_reply_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    comment_reply_template: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    instagram_account: Mapped["InstagramAccount"] = relationship(
        "InstagramAccount",
        back_populates="automations",
    )
    dm_sent_logs: Mapped[list["DMSentLog"]] = relationship(
        "DMSentLog",
        back_populates="automation",
        cascade="all, delete-orphan",
    )
    comment_reply_logs: Mapped[list["CommentReplyLog"]] = relationship(
        "CommentReplyLog",
        back_populates="automation",
        cascade="all, delete-orphan",
    )


class DMSentLog(Base, UUIDMixin):
    """Log of sent DMs for deduplication."""

    __tablename__ = "dm_sent_log"

    automation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    post_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    commenter_user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    comment_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Commenter profile fields
    commenter_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    commenter_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commenter_biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    commenter_followers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commenter_media_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commenter_profile_picture_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    automation: Mapped["Automation"] = relationship(
        "Automation",
        back_populates="dm_sent_logs",
    )


class CommentReplyLog(Base, UUIDMixin):
    """Log of comment replies sent."""

    __tablename__ = "comment_reply_log"

    automation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    post_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    comment_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    commenter_user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # sent | failed
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Commenter profile fields
    commenter_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    commenter_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commenter_biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    commenter_followers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commenter_media_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commenter_profile_picture_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    automation: Mapped["Automation"] = relationship(
        "Automation",
        back_populates="comment_reply_logs",
    )
