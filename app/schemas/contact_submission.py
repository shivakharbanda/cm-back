"""Pydantic schemas for contact form submissions."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class ContactSubmissionCreate(BaseModel):
    """Schema for creating a contact submission."""

    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    subject: str | None = Field(None, max_length=200)
    message: str = Field(..., min_length=1)


class ContactSubmissionResponse(BaseModel):
    """Schema for a contact submission response."""

    id: int
    name: str
    email: str
    subject: str | None
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
