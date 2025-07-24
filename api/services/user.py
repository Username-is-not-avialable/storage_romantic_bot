from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from api.database import User

async def get_user_by_telegram_id(
    telegram_id: int,
    session: AsyncSession
) -> User | None:
    """Получение пользователя по Telegram ID"""
    result = await session.execute(
        select(User).where(User.id_telegram == telegram_id)
    )
    return result.scalars().first()