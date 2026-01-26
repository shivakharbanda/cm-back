"""Pydantic schemas for social links."""

import re
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.social_link import SocialPlatform


# Platform-specific URL patterns
PLATFORM_PATTERNS = {
    SocialPlatform.INSTAGRAM: r"^https?://(www\.)?instagram\.com/[\w.]+/?",
    SocialPlatform.TWITTER: r"^https?://(www\.)?(twitter\.com|x\.com)/[\w]+/?",
    SocialPlatform.YOUTUBE: r"^https?://(www\.)?(youtube\.com|youtu\.be)/(c/|channel/|@)?[\w-]+/?",
    SocialPlatform.TIKTOK: r"^https?://(www\.)?tiktok\.com/@[\w.]+/?",
    SocialPlatform.LINKEDIN: r"^https?://(www\.)?linkedin\.com/(in|company)/[\w-]+/?",
    SocialPlatform.WEBSITE: r"^https?://[\w.-]+\.[a-z]{2,}",
}


def normalize_url(url: str) -> str:
    """Remove tracking parameters and normalize URL."""
    parsed = urlparse(url)
    # Strip query params (removes ?igsh=..., ?utm_source=..., etc.)
    clean = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip('/'),  # Remove trailing slash
        '', '', ''  # No params, query, fragment
    ))
    return clean


class SocialLinkCreate(BaseModel):
    """Schema for creating a social link."""

    platform: SocialPlatform
    url: str = Field(..., min_length=1, max_length=500)

    @model_validator(mode='after')
    def validate_and_normalize_url(self) -> 'SocialLinkCreate':
        """Validate URL matches platform pattern and normalize it."""
        if self.platform in PLATFORM_PATTERNS:
            pattern = PLATFORM_PATTERNS[self.platform]
            if not re.match(pattern, self.url, re.IGNORECASE):
                raise ValueError(f'Invalid {self.platform.value} URL format')
        # Normalize: remove tracking params
        self.url = normalize_url(self.url)
        return self


class SocialLinkUpdate(BaseModel):
    """Schema for updating a social link."""

    url: str | None = Field(None, min_length=1, max_length=500)
    position: int | None = Field(None, ge=0)
    is_active: bool | None = None


class SocialLinkResponse(BaseModel):
    """Schema for social link response."""

    id: UUID
    bio_page_id: UUID
    platform: SocialPlatform
    url: str
    position: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SocialLinkPublicResponse(BaseModel):
    """Schema for public social link response."""

    id: UUID
    platform: SocialPlatform
    url: str

    model_config = {"from_attributes": True}


class SocialLinkReorderItem(BaseModel):
    """Schema for a single item in reorder request."""

    id: UUID
    position: int = Field(..., ge=0)


class SocialLinkReorderRequest(BaseModel):
    """Schema for reordering social links."""

    items: list[SocialLinkReorderItem]
