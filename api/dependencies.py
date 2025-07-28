from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import Gear, Rental, User, get_db
from api.services.gear import get_gear_by_id
from api.services.rental import get_rental_by_id
from api.services.user import get_user_by_telegram_id

async def get_current_user(
    id_telegram: int,
    db: AsyncSession = Depends(get_db)
) -> User:
    user = await get_user_by_telegram_id(id_telegram, db)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    return user



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