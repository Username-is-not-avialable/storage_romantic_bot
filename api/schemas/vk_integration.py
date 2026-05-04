from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RequestVkLinkCodeResponse(BaseModel):
    code: str
    expires_at: datetime


class VkLinkCompleteRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=128)
    vk_user_id: int = Field(..., ge=1)

class VkManagerWithLink(BaseModel):
    """Завснар или администратор для выбора в боте (`target_manager_id` = `user_id`)."""

    user_id: int
    full_name: str
    role: str
    vk_user_id: int | None = Field(
        default=None,
        description="Числовой id VK, если есть привязка user_messenger_links (provider=vk).",
    )


class VkManagersWithVkList(BaseModel):
    managers: list[VkManagerWithLink]
