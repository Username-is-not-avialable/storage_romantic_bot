from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Optional
from datetime import date

class GearBase(BaseModel):
    """Базовая схема снаряжения"""
    name: str = Field(..., min_length=1, max_length=100, example="Палатка 4-местная RF Challenger")
    total_quantity: int = Field(..., gt=0, example=10)
    # available_count: Optional[int] = Field(None)
    available_count: int
    description: Optional[str] = Field(None, max_length=1000, example="Водонепроницаемая, вес 5 кг")

    @model_validator(mode='before')
    def set_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get('available_count') is None:
                data['available_count'] = data['total_quantity']
        return data

    @field_validator('available_count')
    def validate_available_count(cls, v, info):
        if v > info.data['total_quantity']:
            raise ValueError('available_count не может превышать total_quantity')
        return v

class GearCreate(GearBase):
    """Схема для создания снаряжения"""
    pass

class GearResponse(GearBase):
    """Схема для возврата данных о снаряжении"""
    id: int
    available_count: int = Field(..., ge=0, example=7) #duplicates with field in base class

    class Config:
        from_attributes = True  # Для совместимости с ORM (альтернатива orm_mode в Pydantic v2)

class GearSearchResponse(BaseModel):
    """Схема для возврата списка снаряжения"""
    items: list[GearResponse] = Field(..., description="Список элементов снаряжения")

class GearUpdate(BaseModel):
    """Схема для обновления данных снаряжения"""
    name: str = Field(None, min_length=1, max_length=100, example="Кошки жесткие")
    description: str = Field(None, max_length=1000, example="Починены 1.01.2025")
    total_quantity: int = Field(None, gt=0)
    available_count: int = Field(None, ge=0)