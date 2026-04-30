from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import User, get_db
from api.dependencies import require_admin
from api.schemas.user import UserList


router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/users", response_model=UserList)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: User = Depends(require_admin()),
    name: str | None = None,
):
    """Список пользователей для административного интерфейса."""
    q = select(User)
    if name is not None and name.strip():
        q = q.where(User.full_name.ilike(f"%{name.strip()}%"))
    q = q.order_by(User.id_telegram.asc())

    result = await db.execute(q)
    users = result.scalars().all()
    return UserList(users=users)
