"""Pydantic schemas for bio cards."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BioCardCreate(BaseModel):
    """Schema for creating a bio card."""

    badge_text: str | None = Field(None, max_length=30)
    headline: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    background_color: str = Field("#000000", pattern=r"^#[0-9A-Fa-f]{6}$")
    background_image_url: str | None = Field(None, max_length=500)
    cta_text: str = Field(..., min_length=1, max_length=50)
    destination_url: str = Field(..., min_length=1, max_length=2048)
    success_message: str | None = Field(None, max_length=200)
    requires_email: bool = True
    is_active: bool = True
    visible_from: datetime | None = None
    visible_until: datetime | None = None


class BioCardUpdate(BaseModel):
    """Schema for updating a bio card."""

    badge_text: str | None = Field(None, max_length=30)
    headline: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    background_color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    background_image_url: str | None = Field(None, max_length=500)
    cta_text: str | None = Field(None, min_length=1, max_length=50)
    destination_url: str | None = Field(None, min_length=1, max_length=2048)
    success_message: str | None = Field(None, max_length=200)
    requires_email: bool | None = None
    is_active: bool | None = None
    visible_from: datetime | None = None
    visible_until: datetime | None = None


class BioCardResponse(BaseModel):
    """Schema for bio card response."""

    id: UUID
    bio_page_id: UUID
    badge_text: str | None
    headline: str
    description: str | None
    background_color: str
    background_image_url: str | None
    cta_text: str
    destination_url: str
    success_message: str | None
    requires_email: bool
    is_active: bool
    visible_from: datetime | None
    visible_until: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BioCardPublicResponse(BaseModel):
    """Schema for public bio card response."""

    id: UUID
    badge_text: str | None
    headline: str
    description: str | None
    background_color: str
    background_image_url: str | None
    cta_text: str
    requires_email: bool

    model_config = {"from_attributes": True}


class CardSubmitRequest(BaseModel):
    """Schema for card submission (lead capture)."""

    email: str = Field(..., min_length=1, max_length=255)


class CardSubmitResponse(BaseModel):
    """Schema for card submission response."""

    success: bool
    success_message: str | None
    destination_url: str
