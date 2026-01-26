"""Pydantic schemas for leads."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.models.lead import SourceType


class LeadResponse(BaseModel):
    """Schema for lead response."""

    id: UUID
    bio_page_id: UUID
    bio_card_id: UUID | None
    email: str
    phone: str | None
    source_type: SourceType
    metadata: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    """Schema for paginated lead list response."""

    leads: list[LeadResponse]
    total: int
    page: int
    pages: int
