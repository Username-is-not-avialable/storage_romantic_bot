from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str
    document: str | None
    role: str


class AuthMessageResponse(BaseModel):
    message: str


class RequestEmailCodeRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    purpose: str = Field(..., pattern="^(email_verify|password_reset)$")


class VerifyEmailCodeRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    purpose: str = Field(..., pattern="^(email_verify|password_reset)$")
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)
