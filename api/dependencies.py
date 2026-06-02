import secrets
from typing import Annotated, Callable

from fastapi import Cookie, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import Gear, Rental, User, get_db
from api.services.auth import resolve_user_by_session_token
from api.services.gear import get_gear_by_id
from api.services import vk_integration as vk_integration_svc
from api.services.rentals import get_rental_by_id


def verify_vk_bot_secret_header(
    x_vk_bot_secret: str | None = Header(default=None, alias="X-VK-Bot-Secret"),
) -> None:
    """Проверка общего секрета между API и процессом VK-бота."""
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


async def get_user_for_vk_bot(
    vk_user_id: int = Query(..., description="Numeric VK user id from Long Poll / Callback"),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_vk_bot_secret_header),
) -> User:
    user = await vk_integration_svc.get_user_profile_for_vk(db, vk_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="VK account is not linked")
    return user


async def get_rental_applicant_for_vk_bot(current_user: User = Depends(get_user_for_vk_bot)) -> User:
    """Заявки на выдачу/возврат через VK: member, manager, admin."""
    if current_user.role not in ("member", "manager", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return current_user


async def get_manager_for_vk_bot(current_user: User = Depends(get_user_for_vk_bot)) -> User:
    if current_user.role not in ("manager", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return current_user


VkBotUser = Annotated[User, Depends(get_user_for_vk_bot)]
VkBotRentalApplicantUser = Annotated[User, Depends(get_rental_applicant_for_vk_bot)]
VkBotManagerUser = Annotated[User, Depends(get_manager_for_vk_bot)]


def get_session_token(auth_session: str | None = Cookie(default=None)) -> str | None:
    return auth_session


async def get_current_user(
    session_token: str | None = Depends(get_session_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await resolve_user_by_session_token(db, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")
    return user


def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    allowed: set[str] = set(allowed_roles)

    async def _require(current_user: User = Depends(get_current_user)) -> User:
        role = getattr(current_user, "role", None)
        if role not in allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
        return current_user

    return _require


def require_manager_or_admin() -> Callable[[User], User]:
    return require_roles("manager", "admin")


def require_member_or_manager_or_admin() -> Callable[[User], User]:
    """Оформление заявок на выдачу/возврат (веб): те же роли, что у участника-клиента."""
    return require_roles("member", "manager", "admin")


def require_admin() -> Callable[[User], User]:
    return require_roles("admin")



async def get_valid_gear(
    gear_id: int,
    db: AsyncSession = Depends(get_db)
) -> Gear:
    """Проверка существования снаряжения"""
    if gear := await get_gear_by_id(gear_id, db):
        return gear
    raise HTTPException(
        status_code=404,
        detail="Снаряжение не найдено" # TODO: добавить схему ошибки, чтобы в свагере не отображалось как undocumented
    )


async def get_valid_rental(
    rental_id: int,
    db: AsyncSession = Depends(get_db)
) -> Rental:
    if rental := await get_rental_by_id(rental_id, db):
        return rental
    raise HTTPException(status_code=404, detail="Запись о выдаче не найдена")