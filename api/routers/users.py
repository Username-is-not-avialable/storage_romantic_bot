from fastapi import APIRouter, Depends, HTTPException
from api.dependencies import get_current_user
from api.schemas.user import UserCreate, UserResponse, UserUpdate
from api.database import User, get_db
from api.services.auth import hash_password
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.post("/", response_model=UserResponse)
async def add_user(
    user: UserCreate, 
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Добавление пользователя"""
    
    # Проверяем, не существует ли уже пользователь с таким email
    result = await db.execute(select(User).where(User.email == user.email.lower()))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Пользователь с таким email уже существует"
        )
    
    # Создаем объект пользователя для БД
    db_user = User(
        email=user.email.lower(),
        password_hash=hash_password(user.password),
        is_active=user.is_active,
        full_name=user.full_name,
        phone=user.phone,
        document=user.document,
        role=user.role,
    )
    
    # Добавляем в сессию и сохраняем
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user
    

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Получение пользователя по внутреннему идентификатору."""
    
    # Выполняем асинхронный запрос к БД
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    # Если пользователь не найден - возвращаем 404
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Пользователь не найден"
        )
    
    return user
    
    

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user)
):
    """Обновление информации о пользователе"""
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if current_user.role != "admin" and current_user.id != target.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Обновляем только переданные поля
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(target, field, value)

    try:
        await db.commit()
        await db.refresh(target)
        return target
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обновлении: {str(e)}"
        )