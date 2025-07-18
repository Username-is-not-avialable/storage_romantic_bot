from fastapi import APIRouter
from api.schemas.rental import RentalCreate

router = APIRouter(prefix="/api/rentals", tags=["Rentals"])

@router.post("/")
async def add_record(rental: RentalCreate):
    """Добавление записи о выдаче"""
    raise NotImplementedError

@router.get("/active")
async def get_active_rentals(user_id: int | None = None):
    """Активные выдачи"""
    raise NotImplementedError

@router.patch("/{rental_id}/return")
async def update_return_date(rental_id: int):
    """Отметка о возврате"""
    raise NotImplementedError