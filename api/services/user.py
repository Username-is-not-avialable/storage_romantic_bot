from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from api.database import User

async def get_user_by_id(
    user_id: int,
    session: AsyncSession
) -> User | None:
    """Получение пользователя по внутреннему идентификатору."""
    result = await session.execute(
        select(User).where(User.id_telegram == user_id)
    )
    return result.scalars().first()