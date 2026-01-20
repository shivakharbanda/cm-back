"""Automation and DM sent log models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.instagram_account import InstagramAccount


class TriggerType(str, enum.Enum):
    """Automation trigger types."""

    ALL_COMMENTS = "all_comments"
    KEYWORD = "keyword"


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
    dm_message_template: Mapped[str] = mapped_column(Text, nullable=False)
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

    # Relationships
    automation: Mapped["Automation"] = relationship(
        "Automation",
        back_populates="dm_sent_logs",
    )
