"""Pydantic schemas for bio links."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.models.bio_link import LinkType


class BioLinkCreate(BaseModel):
    """Schema for creating a bio link."""

    title: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1, max_length=2048)
    link_type: LinkType = LinkType.STANDARD
    is_active: bool = True
    visible_from: datetime | None = None
    visible_until: datetime | None = None
    thumbnail_url: str | None = Field(None, max_length=500)


class BioLinkUpdate(BaseModel):
    """Schema for updating a bio link."""

    title: str | None = Field(None, min_length=1, max_length=100)
    url: str | None = Field(None, min_length=1, max_length=2048)
    link_type: LinkType | None = None
    is_active: bool | None = None
    visible_from: datetime | None = None
    visible_until: datetime | None = None
    thumbnail_url: str | None = Field(None, max_length=500)


class BioLinkResponse(BaseModel):
    """Schema for bio link response."""

    id: UUID
    bio_page_id: UUID
    title: str
    url: str
    link_type: LinkType
    position: int
    is_active: bool
    visible_from: datetime | None
    visible_until: datetime | None
    thumbnail_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BioLinkPublicResponse(BaseModel):
    """Schema for public bio link response."""

    id: UUID
    title: str
    url: str
    thumbnail_url: str | None

    model_config = {"from_attributes": True}


class URLMetadataRequest(BaseModel):
    """Schema for URL metadata fetch request."""

    url: str = Field(..., min_length=1, max_length=2048)


class URLMetadataResponse(BaseModel):
    """Schema for URL metadata response."""

    title: str | None = None
    description: str | None = None
    image: str | None = None
    site_name: str | None = None
