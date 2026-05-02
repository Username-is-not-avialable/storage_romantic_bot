from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RequestVkLinkCodeResponse(BaseModel):
    code: str
    expires_at: datetime


class VkLinkCompleteRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=128)
    vk_user_id: int = Field(..., ge=1)
