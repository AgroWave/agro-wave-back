"""Pydantic schemas for identity presentation endpoints."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload for user self-registration."""

    email: EmailStr
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8)


class ConfirmEmailRequest(BaseModel):
    """Payload for confirming an email address with a single-use token."""

    token: str = Field(min_length=1)


class LoginRequest(BaseModel):
    """Payload for user authentication."""

    email: EmailStr
    password: str = Field(min_length=1)


class RequestPasswordResetRequest(BaseModel):
    """Payload for requesting a password reset email."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Payload for setting a new password with a reset token."""

    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    """Payload for authenticated password change."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class UserResponse(BaseModel):
    """Public user identity representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: str
    email_confirmed: bool


class AuthTokenResponse(BaseModel):
    """Authentication response returning access token and user info."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
