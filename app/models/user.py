"""User model."""

from typing import TYPE_CHECKING

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.instagram_account import InstagramAccount
    from app.models.bio_page import BioPage


class User(Base, UUIDMixin, TimestampMixin):
    """User model for authentication."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Updated on every password change; access tokens issued before this timestamp are rejected.
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    instagram_accounts: Mapped[list["InstagramAccount"]] = relationship(
        "InstagramAccount",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    bio_page: Mapped["BioPage | None"] = relationship(
        "BioPage",
        back_populates="user",
        uselist=False,
    )
