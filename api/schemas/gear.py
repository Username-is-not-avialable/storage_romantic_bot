from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

class GearBase(BaseModel):
    """Базовая схема снаряжения"""
    name: str = Field(..., min_length=1, max_length=100, example="Палатка 4-местная")
    total_quantity: int = Field(..., gt=0, example=10)
    description: Optional[str] = Field(None, max_length=500, example="Водонепроницаемая, вес 5 кг")

class GearCreate(GearBase):
    """Схема для создания снаряжения"""
    pass

class GearResponse(GearBase):
    """Схема для возврата данных о снаряжении"""
    id: int
    available_count: int = Field(..., ge=0, example=7)

    class Config:
        from_attributes = True  # Для совместимости с ORM (альтернатива orm_mode в Pydantic v2)