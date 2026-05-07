from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class RentalReturnRequestItemCreate(BaseModel):
    gear_id: int = Field(..., json_schema_extra={"example": 1})
    qty_return: int = Field(..., gt=0, json_schema_extra={"example": 1})


class RentalReturnRequestItemResponse(RentalReturnRequestItemCreate):
    pass


class RentalReturnRequestCreate(BaseModel):
    rental_id: int = Field(..., json_schema_extra={"example": 1})
    target_manager_id: Optional[int] = Field(
        default=None,
        description="Внутренний id пользователя-завснара (users.id), если заявка адресована конкретному менеджеру.",
    )
    items: list[RentalReturnRequestItemCreate]


class RentalReturnRequestDecision(BaseModel):
    decision: str = Field(..., json_schema_extra={"example": "approve"})
    comment: str | None = Field(None, max_length=500)


class RentalReturnRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    user_full_name: str
    rental_id: int
    target_manager_id: int | None
    status: str
    created_at: datetime
    decision_comment: str | None = None
    items: list[RentalReturnRequestItemResponse]

    @field_serializer("created_at")
    def _ser_created_at(self, v: datetime) -> str:
        return v.isoformat()


class RentalReturnRequestsList(BaseModel):
    requests: list[RentalReturnRequestResponse]
