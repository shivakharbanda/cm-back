"""Lead model for capturing email/phone from bio cards."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.bio_page import BioPage
    from app.models.bio_card import BioCard


class SourceType(str, enum.Enum):
    """Lead source type enum."""

    CARD = "card"
    WHATSAPP = "whatsapp"
    OTHER = "other"


class Lead(Base, UUIDMixin):
    """Lead model for captured contact information."""

    __tablename__ = "leads"

    bio_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bio_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bio_card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bio_cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SourceType.CARD,
    )
    lead_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, name="metadata"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    bio_page: Mapped["BioPage"] = relationship(
        "BioPage",
        back_populates="leads",
    )
    bio_card: Mapped["BioCard | None"] = relationship(
        "BioCard",
        back_populates="leads",
    )
