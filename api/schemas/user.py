from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

UserRole = Literal["member", "manager", "admin"]

class UserBase(BaseModel):
    id_telegram: int
    full_name: str

class UserCreate(UserBase):
    phone: str
    document: str | None = None
    role: UserRole = "member"

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    phone: str
    document: str | None
    role: UserRole

class UserSearch(BaseModel):
    name: str | None = None
    phone: str | None = None

class UserList(BaseModel):
    users: list[UserResponse]


class UserUpdate(BaseModel):
    """Схема для обновления данных пользователя"""
    full_name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, min_length=5, max_length=20)
    document: str | None = Field(None, max_length=100)
    role: UserRole | None = None

    @model_validator(mode='after')
    def validate_phone(cls, values):
        if values.phone and not values.phone.startswith('+'):
            raise ValueError("Телефон должен начинаться с +")
        return values