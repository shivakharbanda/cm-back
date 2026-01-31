"""Pydantic schemas for automations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.automation import MessageType, TriggerType


class CarouselButton(BaseModel):
    """A button on a carousel card."""

    type: str = "web_url"
    url: str
    title: str = Field(..., min_length=1, max_length=80)


class CarouselElement(BaseModel):
    """A single card in a carousel."""

    title: str = Field(..., min_length=1, max_length=80)
    subtitle: str | None = Field(None, max_length=80)
    image_url: str | None = None
    buttons: list[CarouselButton] = Field(..., min_length=1, max_length=3)


class AutomationCreate(BaseModel):
    """Schema for creating an automation."""

    instagram_account_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    post_id: str = Field(..., min_length=1, max_length=100)
    trigger_type: TriggerType
    keywords: list[str] | None = None
    message_type: MessageType = MessageType.TEXT
    dm_message_template: str | None = None
    carousel_elements: list[CarouselElement] | None = None
    comment_reply_enabled: bool = False
    comment_reply_template: str | None = None

    @model_validator(mode="after")
    def validate_message_content(self):
        if self.message_type == MessageType.TEXT:
            if not self.dm_message_template or not self.dm_message_template.strip():
                raise ValueError("dm_message_template is required for text messages")
        elif self.message_type == MessageType.CAROUSEL:
            if not self.carousel_elements or len(self.carousel_elements) == 0:
                raise ValueError("carousel_elements is required for carousel messages")
            if len(self.carousel_elements) > 10:
                raise ValueError("carousel_elements cannot exceed 10 items")
        return self


class AutomationUpdate(BaseModel):
    """Schema for updating an automation."""

    name: str | None = Field(None, min_length=1, max_length=255)
    trigger_type: TriggerType | None = None
    keywords: list[str] | None = None
    message_type: MessageType | None = None
    dm_message_template: str | None = None
    carousel_elements: list[CarouselElement] | None = None
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
    message_type: MessageType
    dm_message_template: str | None
    carousel_elements: list[CarouselElement] | None
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


class AutomationAnalyticsSummary(BaseModel):
    """Summary metrics for inline display on automation cards."""

    dms_sent: int
    people_reached: int


class DatePoint(BaseModel):
    """Single data point for timeline chart."""

    date: str  # YYYY-MM-DD
    value: int


class AutomationAnalytics(BaseModel):
    """Full analytics data for an automation."""

    automation_id: str
    total_dms_sent: int
    total_dms_failed: int
    dm_success_rate: float  # percentage
    unique_people_reached: int
    total_comment_replies: int
    total_comment_replies_failed: int
    comment_reply_success_rate: float
    dms_by_date: list[DatePoint]
    replies_by_date: list[DatePoint]


class CommenterInfo(BaseModel):
    """Full profile info for a person who received a DM."""

    user_id: str
    username: str | None
    name: str | None
    biography: str | None
    followers_count: int | None
    media_count: int | None
    profile_picture_url: str | None
    dm_sent_at: datetime
    status: str


class AutomationCommentersResponse(BaseModel):
    """List of people who received DMs from an automation."""

    automation_id: str
    commenters: list[CommenterInfo]
    total: int
