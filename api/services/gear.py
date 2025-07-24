from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from api.database import Gear

async def get_gear_by_id(
    gear_id: int,
    session: AsyncSession
) -> Gear | None:
    """Получение снаряжения по ID"""
    result = await session.execute(
        select(Gear).where(Gear.id == gear_id)
    )
    return result.scalars().first()