"""Auth request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=200)


class VerificationSentResponse(BaseModel):
    """Returned by POST /auth/register — tells the client to show the OTP input."""
    message: str
    email: str
    needs_verification: bool = True


class VerifyRegisterRequest(BaseModel):
    """OTP verification step — completes registration and issues JWT."""
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    avatar_url: str | None = None
    github_id: str | None = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ------------------------------------------------------------------ #
# Password reset                                                       #
# ------------------------------------------------------------------ #

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, description="Reset token received by email.")
    new_password: str = Field(min_length=8, description="New password (min 8 characters).")


class VerifyResetRequest(BaseModel):
    """OTP-based password reset — step 2: verify code + set new password."""
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, description="New password (min 8 characters).")


class MessageResponse(BaseModel):
    """Generic success response."""
    message: str


# Legacy aliases (Phase 1 routers)
UserCreate = RegisterRequest
UserOut = UserResponse
