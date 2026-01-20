"""Pydantic schemas for automations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.automation import TriggerType


class AutomationCreate(BaseModel):
    """Schema for creating an automation."""

    instagram_account_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    post_id: str = Field(..., min_length=1, max_length=100)
    trigger_type: TriggerType
    keywords: list[str] | None = None
    dm_message_template: str = Field(..., min_length=1)
    comment_reply_enabled: bool = False
    comment_reply_template: str | None = None


class AutomationUpdate(BaseModel):
    """Schema for updating an automation."""

    name: str | None = Field(None, min_length=1, max_length=255)
    trigger_type: TriggerType | None = None
    keywords: list[str] | None = None
    dm_message_template: str | None = Field(None, min_length=1)
    comment_reply_enabled: bool | None = None
    comment_reply_template: str | None = None


class AutomationResponse(BaseModel):
    """Schema for automation response."""

    id: UUID
    instagram_account_id: UUID
    name: str
    post_id: str
    trigger_type: TriggerType
    keywords: list[str] | None
    dm_message_template: str
    comment_reply_enabled: bool
    comment_reply_template: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DMSentLogResponse(BaseModel):
    """Schema for DM sent log response."""

    id: UUID
    automation_id: UUID
    post_id: str
    commenter_user_id: str
    comment_id: str
    status: str
    sent_at: datetime

    model_config = {"from_attributes": True}
