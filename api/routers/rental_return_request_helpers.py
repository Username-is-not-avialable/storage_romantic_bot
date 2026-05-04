"""Склейка HTTP → сервис → ответ для заявок на возврат (web и `/api/integrations/vk/`)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import RentalReturnRequest, RentalReturnRequestItem, User
from api.schemas.rental_return_request import (
    RentalReturnRequestCreate,
    RentalReturnRequestDecision,
    RentalReturnRequestResponse,
)
from api.services.rental_return_requests import (
    approve_rental_return_request,
    create_rental_return_request,
    get_return_request_by_id,
    reject_rental_return_request,
)


async def rental_return_request_to_response(
    *,
    db: AsyncSession,
    rr: RentalReturnRequest,
) -> RentalReturnRequestResponse:
    items_result = await db.execute(
        select(RentalReturnRequestItem).where(
            RentalReturnRequestItem.rental_return_request_id == rr.id
        )
    )
    items = items_result.scalars().all()

    return RentalReturnRequestResponse(
        id=rr.id,
        user_id=rr.user_id,
        rental_id=rr.rental_id,
        target_manager_id=rr.target_manager_id,
        status=rr.status,
        created_at=rr.created_at,
        decision_comment=rr.decision_comment,
        items=[{"gear_id": it.gear_id, "qty_return": it.qty_return} for it in items],
    )


async def create_rental_return_request_for_user_response(
    db: AsyncSession,
    *,
    user: User,
    body: RentalReturnRequestCreate,
) -> RentalReturnRequestResponse:
    try:
        rr = await create_rental_return_request(
            session=db,
            user_id=user.id,
            rental_id=body.rental_id,
            items=[it.model_dump() for it in body.items],
            target_manager_id=body.target_manager_id,
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    await db.refresh(rr)
    return await rental_return_request_to_response(db=db, rr=rr)


async def manager_decide_rental_return_request_response(
    db: AsyncSession,
    *,
    return_request_id: int,
    manager: User,
    decision: RentalReturnRequestDecision,
) -> RentalReturnRequestResponse:
    rr = await get_return_request_by_id(return_request_id, db)
    if rr is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if rr.status != "pending":
        raise HTTPException(status_code=400, detail="Заявка уже решена")

    try:
        if decision.decision == "approve":
            await approve_rental_return_request(
                session=db,
                req=rr,
                manager=manager,
                manager_comment=decision.comment,
            )
        elif decision.decision == "reject":
            await reject_rental_return_request(
                session=db,
                req=rr,
                manager=manager,
                manager_comment=decision.comment,
            )
        else:
            raise ValueError("Неверное значение decision")
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    await db.refresh(rr)
    return await rental_return_request_to_response(db=db, rr=rr)
