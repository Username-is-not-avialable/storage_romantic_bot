from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.database import Gear, Rental, User, get_db
from api.dependencies import get_current_user, get_valid_rental, require_manager_or_admin
from api.schemas.rental import (
    RentalIssueCreate,
    RentalResponse,
    RentalReturnBody,
    RentalUpdate,
    RentalItemOut,
    RentalsList,
)
from api.services.rentals import (
    get_rental_by_id,
    issue_rental,
    outstanding_by_gear,
    return_rental,
)

router = APIRouter(prefix="/api/rentals", tags=["Rentals"])


async def _build_rental_response(db: AsyncSession, rental: Rental) -> RentalResponse:
    if not rental.items:
        await db.refresh(rental, attribute_names=["items"])
    out_map = await outstanding_by_gear(db, rental)
    items_out: list[RentalItemOut] = []
    for ri in rental.items:
        gear = await db.get(Gear, ri.gear_id)
        gear_name = gear.name if gear else "?"
        items_out.append(
            RentalItemOut(
                gear_id=ri.gear_id,
                gear_name=gear_name,
                qty_issued=ri.qty_issued,
                qty_outstanding=out_map[ri.gear_id],
            )
        )
    return RentalResponse(
        id=rental.id,
        user_id=rental.user_id,
        issue_manager_id=rental.issue_manager_id,
        issue_date=rental.issue_date,
        due_date=rental.due_date,
        event=rental.event,
        comment=rental.comment,
        status=rental.status,
        closed_at=rental.closed_at,
        items=items_out,
    )


@router.post("/issue", response_model=RentalResponse)
async def issue_rental_endpoint(
    body: RentalIssueCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: User = Depends(require_manager_or_admin()),
):
    """Ручная выдача снаряжения (документ + позиции)."""
    lines = [(it.gear_id, it.qty) for it in body.items]
    for user_id in [body.user_id, body.issue_manager_id]:
        user_exists = await db.execute(
            select(User.id_telegram).where(User.id_telegram == user_id).limit(1)
        )
        if user_exists.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail=f"Пользователь с ID {user_id} не найден")

    try:
        rental = await issue_rental(
            session=db,
            user_id=body.user_id,
            issue_manager_id=body.issue_manager_id,
            due_date=body.due_date,
            event=body.event,
            comment=body.comment,
            lines=lines,
            fee_status_snapshot=None,
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    await db.refresh(rental)
    loaded = await get_rental_by_id(rental.id, db)
    assert loaded is not None
    return await _build_rental_response(db, loaded)


@router.get("/active", response_model=RentalsList)
async def get_active_rentals(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: int | None = None,
):
    """Список активных аренд (status=active)."""
    # TODO: вынести формирование sql запроса из роутера в сервис или репозиторий
    q = (
        select(Rental)
        .options(selectinload(Rental.items))
        .where(Rental.status == "active")
    )
    if user_id is not None:
        q = q.where(Rental.user_id == user_id)

    result = await db.execute(q)
    rentals = result.scalars().unique().all()
    out: list[RentalResponse] = []
    for r in rentals:
        out.append(await _build_rental_response(db, r))
    return RentalsList(rentals=out)


@router.get("/debtors", response_model=RentalsList)
async def get_debtors(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: User = Depends(require_manager_or_admin()),
):
    """Список просроченных аренд (status=active и due_date < today)."""
    q = (
        select(Rental)
        .options(selectinload(Rental.items))
        .where(
            Rental.status == "active",
            Rental.due_date < date.today(),
        )
    )
    result = await db.execute(q)
    rentals = result.scalars().unique().all()
    out: list[RentalResponse] = []
    for rental in rentals:
        out.append(await _build_rental_response(db, rental))
    return RentalsList(rentals=out)


@router.get("/history/{user_id}", response_model=RentalsList)
async def get_member_rental_history(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user),
):
    """
    История участника: только объекты Rental, связанные с user_id.
    """
    if current_user.role not in {"manager", "admin"} and current_user.id_telegram != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    q = (
        select(Rental)
        .options(selectinload(Rental.items))
        .where(Rental.user_id == user_id)
        .order_by(Rental.id.desc())
    )
    result = await db.execute(q)
    rentals = result.scalars().unique().all()
    out: list[RentalResponse] = []
    for rental in rentals:
        out.append(await _build_rental_response(db, rental))
    return RentalsList(rentals=out)


@router.patch("/{rental_id}/return", response_model=RentalResponse)
async def return_rental_endpoint(
    rental_id: int,
    body: RentalReturnBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: User = Depends(require_manager_or_admin()),
):
    lines = [(it.gear_id, it.quantity) for it in body.items]
    manager_exists = await db.execute(
        select(User.id_telegram).where(User.id_telegram == body.manager_id).limit(1)
    )
    if manager_exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Менеджер не найден")

    try:
        rental = await return_rental(
            session=db,
            rental_id=rental_id,
            manager_id=body.manager_id,
            lines=lines,
            fee_status_snapshot=body.fee_status_snapshot,
            comment=body.comment,
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    loaded = await get_rental_by_id(rental.id, db)
    assert loaded is not None
    return await _build_rental_response(db, loaded)


@router.patch("/{rental_id}", response_model=RentalResponse)
async def update_rental(
    rental_id: int,
    rental_data: RentalUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    rental: Rental = Depends(get_valid_rental),
    _: User = Depends(require_manager_or_admin()),
):
    """Редактирование полей шапки аренды (без состава)."""
    update_data = rental_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rental, field, value)

    await db.commit()
    loaded = await get_rental_by_id(rental_id, db)
    assert loaded is not None
    return await _build_rental_response(db, loaded)


@router.get("/{rental_id}", response_model=RentalResponse)
async def get_rental(
    rental_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rental = await get_rental_by_id(rental_id, db)
    if rental is None:
        raise HTTPException(status_code=404, detail="Аренда не найдена")
    return await _build_rental_response(db, rental)
