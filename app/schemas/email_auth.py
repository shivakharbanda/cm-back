"""Pydantic schemas for password-reset and email-verification flows."""

from pydantic import BaseModel, EmailStr, Field


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)


class EmailVerifyRequest(BaseModel):
    token: str
