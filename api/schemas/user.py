from pydantic import BaseModel

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