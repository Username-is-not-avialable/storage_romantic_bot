from fastapi import APIRouter, Depends, HTTPException
from api.dependencies import get_current_user
from api.schemas.user import UserCreate, UserResponse, UserUpdate
from api.database import User, get_db
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
    
    # Проверяем, не существует ли уже пользователь с таким id_telegram
    result = await db.execute(select(User).where(User.id_telegram == user.id_telegram))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Пользователь с таким id_telegram уже существует"
        )
    
    # Создаем объект пользователя для БД
    db_user = User(
        id_telegram=user.id_telegram,
        full_name=user.full_name,
        phone=user.phone,
        document=user.document,
        is_manager=user.is_manager
    )
    
    # Добавляем в сессию и сохраняем
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user
    

@router.get("/{id_telegram}", response_model=UserResponse)
async def get_user(
    id_telegram: int,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Получение пользователя по Telegram ID"""
    
    # Выполняем асинхронный запрос к БД
    result = await db.execute(
        select(User).where(User.id_telegram == id_telegram)
    )
    user = result.scalar_one_or_none()
    
    # Если пользователь не найден - возвращаем 404
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Пользователь с указанным Telegram ID не найден"
        )
    
    return user
    
    

@router.patch("/{id_telegram}/document", deprecated=True)
async def update_document(
    id_telegram: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    doc_name: str | None = None,
    current_user: User = Depends(get_current_user)
):
    """
    Обновление документа пользователя
    
    Параметры:
    - id_telegram: ID пользователя в Telegram
    - doc_name: Название документа (опционально)
    - current_user: Авторизованный пользователь (из зависимости)
    """

    # Обновляем документ
    current_user.document = doc_name  # None очистит документ
    
    try:
        await db.commit()
        await db.refresh(current_user)
        return {
            "status": "success",
            "id_telegram": id_telegram,
            "new_document": doc_name
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обновлении: {str(e)}"
        )

@router.get("/{id_telegram}/is_manager")
async def check_manager(
    id_telegram: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user)
):
    """Проверка статуса завснара"""
    return current_user.is_manager


@router.patch("/{id_telegram}", response_model=UserResponse)
async def update_user(
    id_telegram: int,
    user_data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user)
):
    """Обновление информации о пользователе"""

    # Обновляем только переданные поля
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    try:
        await db.commit()
        await db.refresh(current_user)
        return current_user
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обновлении: {str(e)}"
        )