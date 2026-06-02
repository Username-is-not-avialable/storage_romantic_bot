from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from api.database import User, get_db
from api.dependencies import require_manager_or_admin, require_member_or_manager_or_admin
from api.schemas.rental_request import (
    ManagerRentalRequestsList,
    RentalRequestCreate,
    RentalRequestDecision,
    RentalRequestResponse,
    RentalRequestUpdate,
)
from api.routers.rental_request_helpers import (
    create_rental_request_for_user_response,
    manager_decide_rental_request_response,
    rental_request_to_response,
    update_pending_rental_request_for_owner_response,
)
from api.services.rental_requests import build_manager_rental_requests_query

router = APIRouter(prefix="/api/rental-requests", tags=["RentalRequests"])
manager_router = APIRouter(
    prefix="/api/manager/rental-requests", tags=["ManagerRentalRequests"]
)


@router.get("/", response_model=ManagerRentalRequestsList)
async def list_my_rental_requests_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(require_member_or_manager_or_admin()),
    status: Literal["pending", "approved", "rejected"] | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
):
    """Список заявок на выдачу текущего пользователя."""

    q = build_manager_rental_requests_query(
        status=status,
        user_id=current_user.id,
        due_date_from=None,
        due_date_to=None,
        created_from=None,
        created_to=None,
        sort_order=sort_order,
    )
    result = await db.execute(q)
    requests = result.scalars().all()
    return ManagerRentalRequestsList(
        requests=[
            await rental_request_to_response(db=db, rental_request=request)
            for request in requests
        ]
    )


@router.post("/", response_model=RentalRequestResponse)
async def create_rental_request_endpoint(
    body: RentalRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(require_member_or_manager_or_admin()),
):
    """Создает заявку на выдачу снаряжения (статус `pending`)."""

    return await create_rental_request_for_user_response(
        db, user=current_user, body=body
    )


@router.patch("/{rental_request_id}", response_model=RentalRequestResponse)
async def update_rental_request_endpoint(
    rental_request_id: int,
    body: RentalRequestUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(require_member_or_manager_or_admin()),
):
    """Обновляет состав/поля заявки пока она в `pending`."""

    return await update_pending_rental_request_for_owner_response(
        db,
        rental_request_id=rental_request_id,
        owner=current_user,
        body=body,
    )


@manager_router.get("/", response_model=ManagerRentalRequestsList)
async def list_manager_rental_requests_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: User = Depends(require_manager_or_admin()),
    status: Literal["pending", "approved", "rejected"] | None = None,
    target_user_id: int | None = None,
    due_date_from: date | None = None,
    due_date_to: date | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
):
    """Очередь заявок для менеджера с фильтрами и сортировкой."""

    q = build_manager_rental_requests_query(
        status=status,
        user_id=target_user_id,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        created_from=created_from,
        created_to=created_to,
        sort_order=sort_order,
    )
    result = await db.execute(q)
    requests = result.scalars().all()
    return ManagerRentalRequestsList(
        requests=[
            await rental_request_to_response(db=db, rental_request=request)
            for request in requests
        ]
    )


@manager_router.patch("/{rental_request_id}", response_model=RentalRequestResponse)
async def decide_rental_request_endpoint(
    rental_request_id: int,
    decision: RentalRequestDecision,
    db: Annotated[AsyncSession, Depends(get_db)],
    manager: User = Depends(require_manager_or_admin()),
):
    """Принять или отклонить заявку на выдачу; события append-only."""

    return await manager_decide_rental_request_response(
        db,
        rental_request_id=rental_request_id,
        manager=manager,
        decision=decision,
    )
