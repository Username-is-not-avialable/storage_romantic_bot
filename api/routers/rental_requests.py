from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import RentalRequest, RentalRequestItem, User, get_db
from api.dependencies import require_manager_or_admin, require_roles
from api.schemas.rental_request import (
    ManagerRentalRequestsList,
    RentalRequestCreate,
    RentalRequestDecision,
    RentalRequestResponse,
    RentalRequestUpdate,
)
from api.services.rental_requests import (
    approve_rental_request,
    build_manager_rental_requests_query,
    create_rental_request,
    get_rental_request_by_id,
    reject_rental_request,
    update_rental_request_items,
)

router = APIRouter(prefix="/api/rental-requests", tags=["RentalRequests"])
manager_router = APIRouter(
    prefix="/api/manager/rental-requests", tags=["ManagerRentalRequests"]
)


async def _rental_request_to_response(
    *,
    db: AsyncSession,
    rental_request: RentalRequest,
) -> RentalRequestResponse:
    items_result = await db.execute(
        select(RentalRequestItem).where(
            RentalRequestItem.rental_request_id == rental_request.id
        )
    )
    items = items_result.scalars().all()

    return RentalRequestResponse(
        id=rental_request.id,
        user_id=rental_request.user_id,
        created_at=rental_request.created_at,
        due_date=rental_request.due_date,
        event=rental_request.event,
        comment=rental_request.comment,
        deposit_document=rental_request.deposit_document,
        status=rental_request.status,
        decision_comment=rental_request.decision_comment,
        items=[
            {
                "gear_id": it.gear_id,
                "qty_requested": it.qty_requested,
            }
            for it in items
        ],
    )


@router.post("/", response_model=RentalRequestResponse)
async def create_rental_request_endpoint(
    body: RentalRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(require_roles("member")),
):
    """Создает заявку на выдачу снаряжения (статус `pending`)."""

    try:
        rental_request = await create_rental_request(
            session=db,
            user_id=current_user.id_telegram,
            due_date=body.due_date,
            event=body.event,
            comment=body.comment,
            deposit_document=body.deposit_document,
            items=[it.model_dump() for it in body.items],
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    await db.refresh(rental_request)
    return await _rental_request_to_response(db=db, rental_request=rental_request)


@router.patch("/{rental_request_id}", response_model=RentalRequestResponse)
async def update_rental_request_endpoint(
    rental_request_id: int,
    body: RentalRequestUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(require_roles("member")),
):
    """Обновляет состав/поля заявки пока она в `pending`."""

    rental_request = await get_rental_request_by_id(rental_request_id, db)
    if rental_request is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if rental_request.user_id != current_user.id_telegram:
        raise HTTPException(status_code=403, detail="Forbidden")
    if rental_request.status != "pending":
        raise HTTPException(
            status_code=400, detail="Нельзя обновлять заявку после решения"
        )

    update_data = body.model_dump(exclude_unset=True)

    try:
        if "due_date" in update_data:
            rental_request.due_date = update_data["due_date"]
        if "event" in update_data:
            rental_request.event = update_data["event"]
        if "comment" in update_data:
            rental_request.comment = update_data["comment"]
        if "deposit_document" in update_data:
            rental_request.deposit_document = update_data["deposit_document"]
        if "items" in update_data and update_data["items"] is not None:
            await update_rental_request_items(
                session=db,
                rental_request=rental_request,
                items=update_data["items"],
            )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    await db.refresh(rental_request)
    return await _rental_request_to_response(db=db, rental_request=rental_request)


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
            await _rental_request_to_response(db=db, rental_request=request)
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

    rental_request = await get_rental_request_by_id(rental_request_id, db)
    if rental_request is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if rental_request.status != "pending":
        raise HTTPException(status_code=400, detail="Заявка уже решена")

    try:
        if decision.decision == "approve":
            await approve_rental_request(
                session=db,
                rental_request=rental_request,
                manager_id=manager.id_telegram,
                manager_comment=decision.comment,
            )
        elif decision.decision == "reject":
            await reject_rental_request(
                session=db,
                rental_request=rental_request,
                manager_id=manager.id_telegram,
                manager_comment=decision.comment,
            )
        else:
            raise ValueError("Неверное значение decision")
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    await db.refresh(rental_request)
    return await _rental_request_to_response(db=db, rental_request=rental_request)
