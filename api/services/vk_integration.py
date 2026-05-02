from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import User, UserMessengerLink, VkLinkRequest
from api.services.auth import hash_secret


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


CompleteVkLinkError = Literal["invalid_code", "vk_already_linked"]


async def request_vk_link_code(session: AsyncSession, user_id: int) -> tuple[str, datetime]:
    settings = get_settings()
    raw_code = secrets.token_urlsafe(9)
    now = _utc_now()
    expires_at = now + timedelta(minutes=settings.vk_link_ttl_minutes)
    session.add(
        VkLinkRequest(
            user_id=user_id,
            code_hash=hash_secret(raw_code),
            expires_at=expires_at,
            created_at=now,
        )
    )
    await session.flush()
    return raw_code, expires_at


async def complete_vk_link(
    session: AsyncSession,
    *,
    code: str,
    vk_user_id: int,
) -> tuple[User | None, CompleteVkLinkError | None]:
    now = _utc_now()
    code_hash = hash_secret(code)
    result = await session.execute(
        select(VkLinkRequest).where(
            VkLinkRequest.code_hash == code_hash,
            VkLinkRequest.used_at.is_(None),
            VkLinkRequest.expires_at > now,
        )
    )
    link_request = result.scalars().first()
    if link_request is None:
        return None, "invalid_code"

    ext_id = str(vk_user_id)
    existing = await session.execute(
        select(UserMessengerLink).where(
            UserMessengerLink.provider == "vk",
            UserMessengerLink.external_user_id == ext_id,
        )
    )
    row = existing.scalars().first()
    if row is not None and row.user_id != link_request.user_id:
        return None, "vk_already_linked"

    link_request.used_at = now

    if row is not None and row.user_id == link_request.user_id:
        row.linked_at = now
        user = await session.get(User, link_request.user_id)
        assert user is not None
        return user, None

    session.add(
        UserMessengerLink(
            user_id=link_request.user_id,
            provider="vk",
            external_user_id=ext_id,
            linked_at=now,
            is_primary=False,
        )
    )
    await session.flush()
    user = await session.get(User, link_request.user_id)
    assert user is not None
    return user, None


async def get_user_profile_for_vk(session: AsyncSession, vk_user_id: int) -> User | None:
    ext_id = str(vk_user_id)
    result = await session.execute(
        select(User)
        .join(UserMessengerLink, UserMessengerLink.user_id == User.id)
        .where(
            UserMessengerLink.provider == "vk",
            UserMessengerLink.external_user_id == ext_id,
        )
    )
    return result.scalars().first()
