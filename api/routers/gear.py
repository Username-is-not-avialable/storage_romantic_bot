from typing import Annotated
from fastapi import APIRouter, Depends
from api.database import get_db, Gear
from api.schemas.gear import GearCreate, GearResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/gear", tags=["Gear"])

@router.post("/", response_model=GearResponse)
async def add_gear(
    gear: GearCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
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
async def get_gear(gear_id: int):
    """Получение снаряжения по ID"""
    raise NotImplementedError

@router.get("/search")
async def get_gear_by_name(name: str):
    """Поиск по названию"""
    raise NotImplementedError