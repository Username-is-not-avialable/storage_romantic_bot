from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import User, get_db
from api.dependencies import get_current_user
from api.schemas.auth import MeResponse
from api.schemas.vk_integration import RequestVkLinkCodeResponse, VkLinkCompleteRequest
from api.services import vk_integration as vk_svc

auth_vk_router = APIRouter(prefix="/api/auth/vk-link", tags=["Auth"])
integrations_router = APIRouter(prefix="/api/integrations/vk", tags=["VK Integration"])


def _require_vk_bot_secret(x_vk_bot_secret: str | None = Header(default=None, alias="X-VK-Bot-Secret")) -> None:
    settings = get_settings()
    if not settings.vk_bot_secret:
        raise HTTPException(
            status_code=503,
            detail="VK bot integration is not configured: set VK_BOT_SECRET for the API service.",
        )
    if not x_vk_bot_secret:
        raise HTTPException(status_code=401, detail="Missing X-VK-Bot-Secret header")
    expected = settings.vk_bot_secret
    if len(x_vk_bot_secret) != len(expected) or not secrets.compare_digest(x_vk_bot_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid X-VK-Bot-Secret")


@auth_vk_router.post("/request_code", response_model=RequestVkLinkCodeResponse)
async def request_vk_link_code(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code, expires_at = await vk_svc.request_vk_link_code(db, current_user.id)
    await db.commit()
    return RequestVkLinkCodeResponse(code=code, expires_at=expires_at)


@integrations_router.post("/link-complete", response_model=MeResponse)
async def vk_link_complete(
    body: VkLinkCompleteRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_vk_bot_secret),
):
    user, err = await vk_svc.complete_vk_link(db, code=body.code, vk_user_id=body.vk_user_id)
    if err == "invalid_code":
        raise HTTPException(status_code=400, detail="Invalid or expired link code")
    if err == "vk_already_linked":
        raise HTTPException(
            status_code=409,
            detail="This VK account is already linked to another user.",
        )
    assert user is not None
    await db.commit()
    return user


@integrations_router.get("/me", response_model=MeResponse)
async def vk_me(
    vk_user_id: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_vk_bot_secret),
):
    user = await vk_svc.get_user_profile_for_vk(db, vk_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="VK account is not linked")
    return user
