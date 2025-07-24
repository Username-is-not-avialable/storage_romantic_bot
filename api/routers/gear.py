from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from api.database import User, get_db, Gear
from api.dependencies import get_current_user, get_valid_gear
from api.schemas.gear import GearCreate, GearResponse, GearSearchResponse, GearUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select

router = APIRouter(prefix="/api/gear", tags=["Gear"])

@router.post("/", response_model=GearResponse)
async def add_gear(
    gear: GearCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
):

    result = await db.execute(select(Gear).where(Gear.name == gear.name))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Снаряжение с таким названием уже существует"
        )

    """Добавление снаряжения"""
    db_gear = Gear(
        name=gear.name,
        total_quantity=gear.total_quantity,
        available_count=gear.available_count,
        description=gear.description
    )
    
    db.add(db_gear)
    await db.commit()
    await db.refresh(db_gear)
    
    return db_gear

@router.get("/{gear_id}", response_model=GearResponse)
async def get_gear(gear_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    """Получение снаряжения по ID"""
    result = await db.execute(select(Gear).where(Gear.id == gear_id))
    gear = result.scalar_one_or_none()
    if gear is None:
        raise HTTPException(
            status_code=400,
            detail="Снаряжение с таким id не существует"
        )
    
    return gear

@router.get("/search/{name}", response_model=GearSearchResponse)
async def get_gear_by_name(name: str, db: Annotated[AsyncSession, Depends(get_db)]):
    """Поиск по названию"""
    result = await db.execute(
        select(Gear).where(
            or_(
                Gear.name.ilike(f"%{name}%"), 
                Gear.description.ilike(f"%{name}%")
            )
        )
    )
    gear_list = result.scalars().all()

    return GearSearchResponse(items=gear_list)

@router.patch("/{gear_id}", response_model=GearResponse)
async def update_gear(
    gear_id: int,
    gear_data: GearUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    gear: Gear = Depends(get_valid_gear)
):
    """Обновление информации о снаряжении"""

    # Обновляем только переданные поля
    update_data = gear_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(gear, field, value)

    try:
        await db.commit()
        await db.refresh(gear)
        return gear
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обновлении: {str(e)}"
        )