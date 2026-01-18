"""Pydantic schemas for Instagram integration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class InstagramAuthURL(BaseModel):
    """Schema for Instagram OAuth URL response."""

    auth_url: str


class InstagramCallbackRequest(BaseModel):
    """Schema for Instagram OAuth callback."""

    code: str


class InstagramAccountResponse(BaseModel):
    """Schema for Instagram account response."""

    id: UUID
    instagram_user_id: str
    username: str
    token_expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InstagramPostResponse(BaseModel):
    """Schema for Instagram post response."""

    id: str
    caption: str | None = None
    media_type: str
    media_url: str | None = None
    permalink: str | None = None
    thumbnail_url: str | None = None
    timestamp: str | None = None
    username: str | None = None


class InstagramPostsListResponse(BaseModel):
    """Schema for list of Instagram posts."""

    posts: list[InstagramPostResponse]
    next_cursor: str | None = None
