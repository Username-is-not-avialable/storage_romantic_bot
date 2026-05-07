import re
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


def _parse_date_value(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        if re.match(r"^\d{2}\.\d{2}\.\d{4}$", value):
            day, month, year = map(int, value.split("."))
            return date(year, month, day)
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            return date.fromisoformat(value)
    raise ValueError("Дата должна быть в формате дд.мм.гггг или ISO")


class RentalIssueItem(BaseModel):
    gear_id: int = Field(..., gt=0)
    qty: int = Field(..., gt=0)


class RentalIssueCreate(BaseModel):
    """Ручная выдача: документ и позиции."""

    user_id: int = Field(..., json_schema_extra={"example": 12345})
    issue_manager_id: int = Field(..., json_schema_extra={"example": 98765})
    due_date: date = Field(..., json_schema_extra={"example": "20.06.2024"})
    event: str = Field(..., max_length=300, json_schema_extra={"example": "Поход"})
    comment: Optional[str] = Field(None, max_length=300)
    items: list[RentalIssueItem] = Field(..., min_length=1)

    @field_validator("due_date", mode="before")
    @classmethod
    def parse_due_date(cls, value: Any) -> date:
        return _parse_date_value(value)

    model_config = ConfigDict()

    @field_serializer("due_date")
    def _ser_due_date(self, v: date) -> str:
        return v.strftime("%d.%m.%Y")


class RentalReturnItem(BaseModel):
    gear_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


class RentalReturnBody(BaseModel):
    """Возврат по одной или нескольким позициям аренды."""

    items: list[RentalReturnItem] = Field(..., min_length=1)
    manager_id: int
    comment: Optional[str] = Field(None, max_length=300)
    fee_status_snapshot: Optional[str] = Field(None, max_length=20)


class RentalItemOut(BaseModel):
    """Позиция состава с остатком к возврату."""

    model_config = ConfigDict(from_attributes=False)

    gear_id: int
    gear_name: str
    qty_issued: int
    qty_outstanding: int


class RentalResponse(BaseModel):
    """Аренда-документ с составом."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    user_full_name: str
    issue_manager_id: int
    issue_date: date
    due_date: date
    event: str
    comment: Optional[str]
    status: str
    closed_at: datetime | None
    items: list[RentalItemOut]

    @field_serializer("issue_date")
    def _ser_issue_date(self, v: date) -> str:
        return v.strftime("%d.%m.%Y")

    @field_serializer("due_date")
    def _ser_due_date(self, v: date) -> str:
        return v.strftime("%d.%m.%Y")

    @field_serializer("closed_at")
    def _ser_closed(self, v: datetime | None) -> str | None:
        return v.isoformat() if v else None


class RentalsList(BaseModel):
    rentals: list[RentalResponse]


class RentalUpdate(BaseModel):
    """Редактирование только полей шапки (без состава)."""

    user_id: int | None = Field(None, json_schema_extra={"example": 12345})
    due_date: date | None = Field(None, json_schema_extra={"example": "31.12.2024"})
    event: str | None = Field(None, max_length=300)
    comment: str | None = Field(None, max_length=300)

    @field_validator("due_date", mode="before")
    @classmethod
    def parse_due_date(cls, value: Any) -> date | None:
        if value is None:
            return None
        return _parse_date_value(value)

    @field_serializer("due_date")
    def _ser_due_date(self, v: date | None) -> str | None:
        return v.strftime("%d.%m.%Y") if v else None
