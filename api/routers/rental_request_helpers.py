"""Утилиты склейки HTTP → сервис → ответ для заявок на выдачу (web и `/api/integrations/vk/`)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import RentalRequest, RentalRequestItem, User
from api.schemas.rental_request import (
    RentalRequestCreate,
    RentalRequestDecision,
    RentalRequestResponse,
    RentalRequestUpdate,
)
from api.services.rental_requests import (
    approve_rental_request,
    assert_valid_rental_target_manager,
    create_rental_request,
    get_rental_request_by_id,
    reject_rental_request,
    update_rental_request_items,
)


async def rental_request_to_response(
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

    author = await db.get(User, rental_request.user_id)
    user_full_name = author.full_name if author else f"Участник #{rental_request.user_id}"

    return RentalRequestResponse(
        id=rental_request.id,
        user_id=rental_request.user_id,
        user_full_name=user_full_name,
        target_manager_id=rental_request.target_manager_id,
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


async def create_rental_request_for_user_response(
    db: AsyncSession,
    *,
    user: User,
    body: RentalRequestCreate,
) -> RentalRequestResponse:
    try:
        rental_request = await create_rental_request(
            session=db,
            user_id=user.id,
            due_date=body.due_date,
            event=body.event,
            comment=body.comment,
            deposit_document=body.deposit_document,
            target_manager_id=body.target_manager_id,
            items=[it.model_dump() for it in body.items],
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    await db.refresh(rental_request)
    return await rental_request_to_response(db=db, rental_request=rental_request)


async def update_pending_rental_request_for_owner_response(
    db: AsyncSession,
    *,
    rental_request_id: int,
    owner: User,
    body: RentalRequestUpdate,
) -> RentalRequestResponse:
    rental_request = await get_rental_request_by_id(rental_request_id, db)
    if rental_request is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if rental_request.user_id != owner.id:
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
        if "target_manager_id" in update_data and update_data["target_manager_id"] is not None:
            await assert_valid_rental_target_manager(
                db, update_data["target_manager_id"]
            )
            rental_request.target_manager_id = update_data["target_manager_id"]
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
    return await rental_request_to_response(db=db, rental_request=rental_request)


async def manager_decide_rental_request_response(
    db: AsyncSession,
    *,
    rental_request_id: int,
    manager: User,
    decision: RentalRequestDecision,
) -> RentalRequestResponse:
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
                manager_id=manager.id,
                manager_comment=decision.comment,
            )
        elif decision.decision == "reject":
            await reject_rental_request(
                session=db,
                rental_request=rental_request,
                manager_id=manager.id,
                manager_comment=decision.comment,
            )
        else:
            raise ValueError("Неверное значение decision")
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    await db.refresh(rental_request)
    return await rental_request_to_response(db=db, rental_request=rental_request)
