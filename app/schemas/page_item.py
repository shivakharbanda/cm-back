"""Pydantic schemas for page items (unified ordering)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.models.page_item import ItemType


class PageItemResponse(BaseModel):
    """Schema for page item response."""

    id: UUID
    bio_page_id: UUID
    item_type: ItemType
    item_id: UUID
    position: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PageItemWithData(BaseModel):
    """Schema for page item with associated data."""

    type: ItemType
    item_id: UUID
    position: int
    data: dict[str, Any]


class ReorderItem(BaseModel):
    """Schema for a single item in reorder request."""

    type: ItemType
    item_id: UUID


class ReorderRequest(BaseModel):
    """Schema for reordering page items."""

    items: list[ReorderItem]


class PageItemsResponse(BaseModel):
    """Schema for ordered page items response."""

    items: list[PageItemWithData]
