import re
from pydantic import BaseModel, Field, field_validator, validator
from datetime import date, datetime
from typing import Any, Optional

class RentalBase(BaseModel):
    """Базовая схема аренды"""
    user_telegram_id: int = Field(..., example=12345)
    gear_id: int = Field(..., example=1)
    quantity: int = Field(..., gt=0, example=2)
    due_date: date = Field(..., example="2024-06-20")
    event: Optional[str] = Field(None, max_length=100, example="Поход на Эльбрус")
    comment: Optional[str] = Field(None, max_length=500, example="Срочно!")

    @field_validator('due_date', mode='before')
    @classmethod
    def parse_due_date(cls, value: Any) -> date:
        if isinstance(value, date):
            return value
            
        if isinstance(value, str):
            # Проверяем формат дд.мм.гггг
            if re.match(r'^\d{2}\.\d{2}\.\d{4}$', value):
                day, month, year = map(int, value.split('.'))
                return date(year, month, day)
            # Также поддерживаем стандартный формат для обратной совместимости
            elif re.match(r'^\d{4}-\d{2}-\d{2}$', value):
                return date.fromisoformat(value)
        
        raise ValueError('Дата должна быть в формате дд.мм.гггг')

    model_config = {
        "json_encoders": {
            date: lambda v: v.strftime('%d.%m.%Y') if v else None
        }
    }

class RentalCreate(RentalBase):
    """Схема для создания записи об аренде"""
    issue_manager_tg_id: int = Field(..., example=98765)


class RentalReturn(BaseModel):
    """Cхема для записи о сдаче снаряжения"""
    rental_id: int


class RentalResponse(RentalBase):
    """Схема для возврата данных об аренде"""
    id: int
    issue_manager_tg_id: int
    accept_manager_tg_id: int | None
    issue_date: date
    return_date: date | None
    gear_name: str = Field(..., example="палатка red fox")
    
    class Config:
        from_attributes = True

class RentalsList(BaseModel):
    rentals: list[RentalResponse]

class RentalUpdate(BaseModel):
    user_telegram_id: int | None = Field(None, example=12345)
    gear_id: int | None = Field(None, example=1)
    due_date: date | None = Field(None, example="2024-12-31")
    event: str | None = Field(None, max_length=100)
    comment: str | None = Field(None, max_length=500)