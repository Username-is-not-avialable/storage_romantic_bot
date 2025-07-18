from fastapi import APIRouter
from api.schemas.gear import GearCreate, GearResponse

router = APIRouter(prefix="/api/gear", tags=["Gear"])

@router.post("/", response_model=GearResponse)
async def add_gear(gear: GearCreate):
    """Добавление снаряжения"""
    raise NotImplementedError

@router.get("/{gear_id}", response_model=GearResponse)
async def get_gear(gear_id: int):
    """Получение снаряжения по ID"""
    raise NotImplementedError

@router.get("/search")
async def get_gear_by_name(name: str):
    """Поиск по названию"""
    raise NotImplementedError