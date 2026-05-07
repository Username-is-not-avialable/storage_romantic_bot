from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import RentalReturnRequest, User, get_db
from api.dependencies import require_manager_or_admin, require_rental_request_submitter
from api.schemas.rental_return_request import (
    RentalReturnRequestCreate,
    RentalReturnRequestDecision,
    RentalReturnRequestResponse,
    RentalReturnRequestsList,
)
from api.routers.rental_return_request_helpers import (
    create_rental_return_request_for_user_response,
    manager_decide_rental_return_request_response,
    rental_return_request_to_response,
)

router = APIRouter(
    prefix="/api/rental-return-requests",
    tags=["RentalReturnRequests"],
)
manager_router = APIRouter(
    prefix="/api/manager/rental-return-requests",
    tags=["ManagerRentalReturnRequests"],
)


@router.get("/", response_model=RentalReturnRequestsList)
async def list_my_rental_return_requests_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(require_rental_request_submitter()),
    status: Literal["pending", "approved", "rejected"] | None = None,
):
    """Список заявок на возврат текущего пользователя."""

    q = select(RentalReturnRequest).where(RentalReturnRequest.user_id == current_user.id)
    if status is not None:
        q = q.where(RentalReturnRequest.status == status)
    q = q.order_by(desc(RentalReturnRequest.created_at))
    result = await db.execute(q)
    rows = result.scalars().all()
    return RentalReturnRequestsList(
        requests=[await rental_return_request_to_response(db=db, rr=rr) for rr in rows]
    )


@manager_router.get("/", response_model=RentalReturnRequestsList)
async def list_manager_rental_return_requests_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: User = Depends(require_manager_or_admin()),
    status: Literal["pending", "approved", "rejected"] | None = None,
    user_id: int | None = None,
):
    """Очередь заявок на возврат для завснара."""

    q = select(RentalReturnRequest)
    if status is not None:
        q = q.where(RentalReturnRequest.status == status)
    if user_id is not None:
        q = q.where(RentalReturnRequest.user_id == user_id)
    q = q.order_by(desc(RentalReturnRequest.created_at))
    result = await db.execute(q)
    rows = result.scalars().all()
    return RentalReturnRequestsList(
        requests=[await rental_return_request_to_response(db=db, rr=rr) for rr in rows]
    )


@router.post("/", response_model=RentalReturnRequestResponse)
async def create_rental_return_request_endpoint(
    body: RentalReturnRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(require_rental_request_submitter()),
):
    """Создаёт заявку на возврат (статус `pending`)."""

    return await create_rental_return_request_for_user_response(
        db, user=current_user, body=body
    )


@manager_router.patch("/{return_request_id}", response_model=RentalReturnRequestResponse)
async def decide_rental_return_request_endpoint(
    return_request_id: int,
    decision: RentalReturnRequestDecision,
    db: Annotated[AsyncSession, Depends(get_db)],
    manager: User = Depends(require_manager_or_admin()),
):
    """Принять или отклонить заявку на возврат."""

    return await manager_decide_rental_return_request_response(
        db,
        return_request_id=return_request_id,
        manager=manager,
        decision=decision,
    )
