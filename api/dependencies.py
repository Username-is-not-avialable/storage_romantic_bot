from typing import Callable

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import Gear, Rental, User, get_db
from api.services.gear import get_gear_by_id
from api.services.auth import resolve_user_by_session_token
from api.services.rentals import get_rental_by_id


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