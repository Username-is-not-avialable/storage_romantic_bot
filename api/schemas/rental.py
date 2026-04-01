import re
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from datetime import date, datetime
from typing import Any, Optional

class RentalBase(BaseModel):
    """Базовая схема аренды"""
    user_telegram_id: int = Field(..., json_schema_extra={"example": 12345})
    gear_id: int = Field(..., json_schema_extra={"example": 1})
    quantity: int = Field(..., gt=0, json_schema_extra={"example": 2})
    due_date: date = Field(..., json_schema_extra={"example": "20.06.2024"})
    event: Optional[str] = Field(
        None, max_length=100, json_schema_extra={"example": "Поход на Эльбрус"}
    )
    comment: Optional[str] = Field(None, max_length=500, json_schema_extra={"example": "Срочно!"})

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

    model_config = ConfigDict()

    @field_serializer("due_date")
    def _ser_due_date(self, v: date) -> str:
        return v.strftime("%d.%m.%Y")

class RentalCreate(RentalBase):
    """Схема для создания записи об аренде"""
    issue_manager_tg_id: int = Field(..., json_schema_extra={"example": 98765})


class RentalReturn(BaseModel):
    """Cхема для записи о сдаче снаряжения"""
    rental_id: int


class RentalResponse(RentalBase):
    """Схема для возврата данных об аренде"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_manager_tg_id: int
    accept_manager_tg_id: int | None
    issue_date: date
    return_date: date | None
    gear_name: str = Field(..., json_schema_extra={"example": "палатка red fox"})

    @field_serializer("issue_date")
    def _ser_issue_date(self, v: date) -> str:
        return v.strftime("%d.%m.%Y")

    @field_serializer("return_date")
    def _ser_return_date(self, v: date | None) -> str | None:
        return v.strftime("%d.%m.%Y") if v else None

class RentalsList(BaseModel):
    rentals: list[RentalResponse]

class RentalUpdate(BaseModel):
    user_telegram_id: int | None = Field(None, json_schema_extra={"example": 12345})
    gear_id: int | None = Field(None, json_schema_extra={"example": 1})
    due_date: date | None = Field(None, json_schema_extra={"example": "31.12.2024"})
    event: str | None = Field(None, max_length=100)
    comment: str | None = Field(None, max_length=500)

    @field_serializer("due_date")
    def _ser_due_date(self, v: date | None) -> str | None:
        return v.strftime("%d.%m.%Y") if v else None
