from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from api.database import User, get_db, Gear
from api.dependencies import get_valid_gear, require_manager_or_admin
from api.schemas.gear import GearCreate, GearResponse, GearSearchResponse, GearUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select

router = APIRouter(prefix="/api/gear", tags=["Gear"])


@router.get("/", response_model=GearSearchResponse)
async def list_gear(
    db: Annotated[AsyncSession, Depends(get_db)],
    query: str | None = None,
    page: int = 1,
    limit: int = 20,
):
    """Список снаряжения с поиском и пагинацией."""
    if query is not None and len(query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Параметр query должен содержать минимум 3 символа")
    if page < 1:
        raise HTTPException(status_code=400, detail="Параметр page должен быть >= 1")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="Параметр limit должен быть в диапазоне 1..100")

    q = select(Gear)
    if query:
        q = q.where(
            or_(
                Gear.name.ilike(f"%{query}%"),
                Gear.description.ilike(f"%{query}%"),
            )
        )

    q = q.order_by(Gear.id.asc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    items = result.scalars().all()
    return GearSearchResponse(items=items)

@router.post("/", response_model=GearResponse)
async def add_gear(
    gear: GearCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: User = Depends(require_manager_or_admin()),
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

@router.patch("/{gear_id}", response_model=GearResponse)
async def update_gear(
    gear_id: int,
    gear_data: GearUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    gear: Gear = Depends(get_valid_gear),
    _: User = Depends(require_manager_or_admin()),
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