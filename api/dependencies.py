from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import User, get_db
from api.services.user import get_user_by_telegram_id

async def get_current_user(
    id_telegram: int,
    db: AsyncSession = Depends(get_db)
) -> User:
    user = await get_user_by_telegram_id(id_telegram, db)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    return user