from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from api.database import Rental

async def get_rental_by_id(
    rental_id: int, 
    session: AsyncSession
) -> Rental | None:
    result = await session.execute(
        select(Rental).where(Rental.id == rental_id)
    )
    return result.scalars().first()