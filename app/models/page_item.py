"""Page item model for unified ordering of links and cards."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.bio_page import BioPage


class ItemType(str, enum.Enum):
    """Item type enum for page items."""

    LINK = "link"
    CARD = "card"


class PageItem(Base, UUIDMixin):
    """Page item model for unified ordering of links and cards."""

    __tablename__ = "page_items"
    __table_args__ = (
        UniqueConstraint(
            "bio_page_id", "item_type", "item_id",
            name="uq_page_items_bio_page_item"
        ),
    )

    bio_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bio_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_type: Mapped[ItemType] = mapped_column(
        Enum(ItemType, name="item_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    bio_page: Mapped["BioPage"] = relationship(
        "BioPage",
        back_populates="page_items",
    )
