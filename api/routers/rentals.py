from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import Gear, Rental, User, get_db
from api.dependencies import get_valid_rental
from api.schemas.rental import RentalCreate, RentalResponse, RentalUpdate, RentalsList
from datetime import datetime, timezone

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
    
    # Сохраняем название снаряжения до коммита
    gear_name = gear.name
    
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
    
    # Добавляем название снаряжения к ответу
    response_data = {
        **{key: getattr(db_rental, key) for key in db_rental.__mapper__.attrs.keys()},
        'gear_name': gear_name
    }
    
    return response_data
    

@router.get("/active", response_model=RentalsList)
async def get_active_rentals(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: int | None = None
):
    """Получение списка активных выдач снаряжения"""
    query = select(Rental, Gear.name.label('gear_name')).join(
        Gear, Rental.gear_id == Gear.id
    ).where(
        Rental.return_date.is_(None)  # Ищем записи без даты возврата
    )
    
    if user_id is not None:
        query = query.where(Rental.user_telegram_id == user_id)
    
    result = await db.execute(query)
    rentals_with_gear = result.all()
    
    # Преобразуем результат в список словарей с объединенными полями
    rentals = []
    for rental, gear_name in rentals_with_gear:
        rental_dict = {
            **{key: getattr(rental, key) for key in rental.__mapper__.attrs.keys()},
            'gear_name': gear_name
        }
        rentals.append(rental_dict)
    
    return RentalsList(rentals=rentals)

@router.patch("/{rental_id}/return", response_model=RentalResponse)
async def update_return_date(
    rental_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    quantity: int = Query(default=None, description="количество единиц возвращаемого снаряжения данного типа"),
    manager_tg_id: int = Query(..., description="ID менеджера, подтверждающего возврат"),
):
    """Отметка о возврате снаряжения"""
    # Получаем запись об аренде с названием снаряжения
    result = await db.execute(
        select(Rental, Gear.name.label('gear_name'))
        .join(Gear, Rental.gear_id == Gear.id)
        .where(Rental.id == rental_id)
    )
    rental_data = result.first()
    
    if not rental_data:
        raise HTTPException(status_code=404, detail="Запись об аренде не найдена")
    
    rental, gear_name = rental_data

    # Проверяем менеджера
    manager_exists = await db.execute(
        select(exists().where(User.id_telegram == manager_tg_id))
    )
    if not manager_exists.scalar():
        raise HTTPException(status_code=404, detail="Менеджер не найден")
    if quantity is None:
        quantity = rental.quantity

    if rental.return_date is not None:
        raise HTTPException(status_code=400, detail="Данное снаряжение уже полностью возвращено")

    if quantity > rental.quantity:
        raise HTTPException(status_code=400, detail=f"Нельзя вернуть больше снаряжения, чем было взято. "
                            + f"Вы пытаетесь вернуть: {quantity}. Можно вернуть: {rental.quantity}.")

    if rental.quantity == quantity:
        # Обновляем данные
        rental.return_date = datetime.now(timezone.utc)
        rental.accept_manager_tg_id = manager_tg_id
    else:
        rental.quantity -= quantity
        #TODO: добавить функцию записи события сдачи не всей снаряги в комментарий к записи об аренде

    # Возвращаем снаряжение в доступное количество
    gear = await db.get(Gear, rental.gear_id)
    if gear:
        gear.available_count += quantity

    await db.commit()
    await db.refresh(rental)
    
    # Добавляем название снаряжения к ответу
    response_data = {
        **{key: getattr(rental, key) for key in rental.__mapper__.attrs.keys()},
        'gear_name': gear_name
    }
    
    return response_data


@router.patch("/{rental_id}", response_model=RentalResponse)
async def update_rental(
    rental_id: int,
    rental_data: RentalUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    rental: Rental = Depends(get_valid_rental)
):
    update_data = rental_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rental, field, value)
    
    await db.commit()
    await db.refresh(rental)
    
    # Получаем название снаряжения
    result = await db.execute(
        select(Gear.name).where(Gear.id == rental.gear_id)
    )
    gear_name = result.scalar()
    
    # Добавляем название снаряжения к ответу
    response_data = {
        **{key: getattr(rental, key) for key in rental.__mapper__.attrs.keys()},
        'gear_name': gear_name
    }
    
    return response_data
