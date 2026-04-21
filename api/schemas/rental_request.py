import re
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


def _parse_due_date(value: Any) -> date:
    if isinstance(value, date):
        return value

    if isinstance(value, str):
        # Поддерживаем формат дд.мм.гггг
        if re.match(r"^\d{2}\.\d{2}\.\d{4}$", value):
            day, month, year = map(int, value.split("."))
            return date(year, month, day)

        # И стандартный ISO
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            return date.fromisoformat(value)

    raise ValueError("Дата должна быть в формате дд.мм.гггг")


class RentalRequestItemBase(BaseModel):
    gear_id: int = Field(..., json_schema_extra={"example": 1})
    qty_requested: int = Field(..., gt=0, json_schema_extra={"example": 2})


class RentalRequestItemCreate(RentalRequestItemBase):
    pass


class RentalRequestItemResponse(RentalRequestItemBase):
    pass


class RentalRequestBase(BaseModel):
    due_date: date = Field(..., json_schema_extra={"example": "20.06.2024"})
    event: str = Field(..., min_length=1, max_length=100, json_schema_extra={"example": "Поход на Эльбрус"})
    comment: Optional[str] = Field(None, max_length=500, json_schema_extra={"example": "Срочно!"})
    deposit_document: Optional[str] = Field(None, max_length=300, json_schema_extra={"example": "расчет_залог_от_2026_04_01.pdf"})

    @field_validator("due_date", mode="before")
    @classmethod
    def parse_due_date(cls, value: Any) -> date:
        return _parse_due_date(value)

    @field_serializer("due_date")
    def _ser_due_date(self, v: date) -> str:
        return v.strftime("%d.%m.%Y")


class RentalRequestCreate(RentalRequestBase):
    items: list[RentalRequestItemCreate]


class RentalRequestUpdate(BaseModel):
    due_date: date | None = Field(None, json_schema_extra={"example": "31.12.2024"})
    event: str | None = Field(None, min_length=1, max_length=100)
    comment: str | None = Field(None, max_length=500)
    deposit_document: str | None = Field(None, max_length=300)
    items: list[RentalRequestItemCreate] | None = None

    @field_validator("due_date", mode="before")
    @classmethod
    def parse_due_date(cls, value: Any) -> date | None:
        if value is None:
            return None
        return _parse_due_date(value)

    @field_serializer("due_date")
    def _ser_due_date(self, v: date | None) -> str | None:
        return v.strftime("%d.%m.%Y") if v else None


class RentalRequestDecision(BaseModel):
    decision: str = Field(..., json_schema_extra={"example": "approve"})
    comment: str | None = Field(None, max_length=500)


class RentalRequestResponse(RentalRequestBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_telegram_id: int
    status: str
    decision_comment: str | None = None
    items: list[RentalRequestItemResponse]

