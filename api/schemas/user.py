from pydantic import BaseModel, Field, model_validator

class UserBase(BaseModel):
    id_telegram: int
    full_name: str

class UserCreate(UserBase):
    phone: str
    document: str | None = None
    is_manager: bool = False

class UserResponse(UserBase):
    phone: str
    document: str | None
    is_manager: bool

class UserUpdate(BaseModel):
    """Схема для обновления данных пользователя"""
    full_name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, min_length=5, max_length=20)
    document: str | None = Field(None, max_length=100)
    is_manager: bool | None = None

    @model_validator(mode='after')
    def validate_phone(cls, values):
        if values.phone and not values.phone.startswith('+'):
            raise ValueError("Телефон должен начинаться с +")
        return values