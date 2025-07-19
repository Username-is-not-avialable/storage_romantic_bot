from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import Gear, Rental, User, get_db
from api.schemas.rental import RentalCreate, RentalResponse, RentalsList

router = APIRouter(prefix="/api/rentals", tags=["Rentals"])

@router.post("/", response_model=RentalResponse)
async def add_record(rental: RentalCreate, 
                     db: Annotated[AsyncSession, Depends(get_db)]):
    """Добавление записи о выдаче снаряжения"""
        # Проверка существования снаряжения
    gear = await db.get(Gear, rental.gear_id)
    if not gear:
        raise HTTPException(status_code=404, detail="Снаряжение не найдено")
    
    # Проверка доступного количества
    if rental.quantity > gear.available_count:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно снаряжения. Доступно: {gear.available_count}"
        )
    
    # Проверка существования пользователя и менеджера
    for tg_id in [rental.user_telegram_id, rental.issue_manager_tg_id]:
        user_exists = await db.execute(
            select(exists().where(User.id_telegram == tg_id))
        )
        if not user_exists.scalar():
            raise HTTPException(status_code=404, detail=f"Пользователь с ID {tg_id} не найден")
    
    # Создание записи об аренде
    db_rental = Rental(
        user_telegram_id=rental.user_telegram_id,
        issue_manager_tg_id=rental.issue_manager_tg_id,
        gear_id=rental.gear_id,
        due_date=rental.due_date,
        quantity=rental.quantity,
        event=rental.event,
        comment=rental.comment
    )
    
    # Обновление доступного количества снаряжения
    gear.available_count -= rental.quantity
    
    db.add(db_rental)
    db.add(gear)
    await db.commit()
    await db.refresh(db_rental)
    
    return db_rental
    

@router.get("/active", response_model=RentalsList)
async def get_active_rentals(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: int | None = None
):
    """Получение списка активных выдач снаряжения"""
    query = select(Rental).where(
        Rental.return_date.is_(None)  # Ищем записи без даты возврата
    )
    
    if user_id is not None:
        query = query.where(Rental.user_telegram_id == user_id)
    
    result = await db.execute(query)
    rentals = result.scalars().all()
    
    return RentalsList(rentals=rentals)

@router.patch("/{rental_id}/return", response_model=RentalResponse)
async def update_return_date(rental_id: int):
    """Отметка о возврате"""
    raise NotImplementedError