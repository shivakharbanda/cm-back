"""Pydantic schemas for notification subscriptions."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class NotificationSubscriptionCreate(BaseModel):
    email: EmailStr
    notification_type: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=200)


class NotificationSubscriptionResponse(BaseModel):
    id: int
    email: str
    notification_type: str
    label: str
    created_at: datetime

    model_config = {"from_attributes": True}
