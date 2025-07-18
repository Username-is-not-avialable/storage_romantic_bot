from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

class RentalBase(BaseModel):
    """Базовая схема аренды"""
    user_telegram_id: int = Field(..., example=12345)
    gear_id: int = Field(..., example=1)
    quantity: int = Field(..., gt=0, example=2)
    due_date: date = Field(..., example="2024-06-20")
    event: Optional[str] = Field(None, max_length=100, example="Поход на Эльбрус")
    comment: Optional[str] = Field(None, max_length=300, example="Срочно!")

class RentalCreate(RentalBase):
    """Схема для создания записи об аренде"""
    manager_telegram_id: int = Field(..., example=98765)

class RentalResponse(RentalBase):
    """Схема для возврата данных об аренде"""
    id: int
    issue_date: date
    manager_telegram_id: int
    return_date: Optional[date] = None

    class Config:
        from_attributes = True