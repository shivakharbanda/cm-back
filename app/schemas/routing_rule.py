"""Pydantic schemas for routing rules."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.routing_rule import RuleType


class RoutingRuleCreate(BaseModel):
    """Schema for creating a routing rule."""

    rule_type: RuleType
    rule_config: dict[str, Any] = Field(
        ...,
        description=(
            "Configuration for the rule. "
            "For country: {'countries': ['US', 'CA']}. "
            "For device: {'devices': ['mobile', 'desktop']}. "
            "For time: {'start_hour': 9, 'end_hour': 17, 'timezone': 'UTC', 'days': [1,2,3,4,5]}"
        )
    )
    destination_url: str = Field(..., min_length=1, max_length=2048)
    priority: int = Field(0, ge=0)
    is_active: bool = True


class RoutingRuleUpdate(BaseModel):
    """Schema for updating a routing rule."""

    rule_type: RuleType | None = None
    rule_config: dict[str, Any] | None = None
    destination_url: str | None = Field(None, min_length=1, max_length=2048)
    priority: int | None = Field(None, ge=0)
    is_active: bool | None = None


class RoutingRuleResponse(BaseModel):
    """Schema for routing rule response."""

    id: UUID
    bio_link_id: UUID
    rule_type: RuleType
    rule_config: dict[str, Any]
    destination_url: str
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
