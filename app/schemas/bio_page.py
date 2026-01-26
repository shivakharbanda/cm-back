"""Pydantic schemas for bio pages."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.social_link import SocialPlatform


class BioPageCreate(BaseModel):
    """Schema for creating a bio page."""

    slug: str | None = None  # Auto-generate if not provided


class SocialLinkInput(BaseModel):
    """Social link input for bio page update."""

    id: UUID | None = None  # None for new, UUID for existing
    platform: SocialPlatform
    url: str
    is_active: bool = True


class BioPageUpdate(BaseModel):
    """Schema for updating a bio page."""

    slug: str | None = Field(None, min_length=1, max_length=50)
    display_name: str | None = Field(None, max_length=100)
    bio_text: str | None = None
    profile_image_url: str | None = Field(None, max_length=500)
    theme_config: dict[str, Any] | None = None
    seo_title: str | None = Field(None, max_length=70)
    seo_description: str | None = Field(None, max_length=160)
    og_image_url: str | None = Field(None, max_length=500)
    social_links: list[SocialLinkInput] | None = None


class BioPageResponse(BaseModel):
    """Schema for bio page response."""

    id: UUID
    user_id: UUID
    instagram_account_id: UUID | None
    slug: str
    display_name: str | None
    bio_text: str | None
    profile_image_url: str | None
    theme_config: dict[str, Any] | None
    is_published: bool
    seo_title: str | None
    seo_description: str | None
    og_image_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BioPagePublicResponse(BaseModel):
    """Schema for public bio page response (no sensitive data)."""

    slug: str
    display_name: str | None
    bio_text: str | None
    profile_image_url: str | None
    theme_config: dict[str, Any] | None
    seo_title: str | None
    seo_description: str | None
    og_image_url: str | None

    model_config = {"from_attributes": True}
