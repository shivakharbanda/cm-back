"""Routing rule model for smart links."""

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.bio_link import BioLink


class RuleType(str, enum.Enum):
    """Routing rule type enum."""

    COUNTRY = "country"
    DEVICE = "device"
    TIME = "time"


class RoutingRule(Base, UUIDMixin, TimestampMixin):
    """Routing rule model for smart link destination selection."""

    __tablename__ = "routing_rules"

    bio_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bio_links.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_type: Mapped[RuleType] = mapped_column(
        Enum(RuleType, name="rule_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    rule_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    destination_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    bio_link: Mapped["BioLink"] = relationship(
        "BioLink",
        back_populates="routing_rules",
    )
