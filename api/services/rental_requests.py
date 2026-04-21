from __future__ import annotations

from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import Gear, Rental, RentalRequest, RentalRequestItem


async def get_rental_request_by_id(
    rental_request_id: int,
    session: AsyncSession,
) -> RentalRequest | None:
    result = await session.execute(
        select(RentalRequest).where(RentalRequest.id == rental_request_id)
    )
    return result.scalars().first()


async def create_rental_request(
    *,
    session: AsyncSession,
    user_telegram_id: int,
    due_date,
    event: str,
    comment: str | None,
    deposit_document: str | None,
    items: Iterable[dict],
) -> RentalRequest:
    """
    Создает заявку (статус pending).

    items ожидает элементы вида: {"gear_id": int, "qty_requested": int}
    """

    items_list = list(items)
    if not items_list:
        raise ValueError("Заявка должна содержать хотя бы одну позицию")

    gear_ids = {int(item["gear_id"]) for item in items_list}
    gear_result = await session.execute(select(Gear).where(Gear.id.in_(gear_ids)))
    gears = {g.id: g for g in gear_result.scalars().all()}
    missing = gear_ids - set(gears.keys())
    if missing:
        raise ValueError("Снаряжение не найдено")

    rental_request = RentalRequest(
        user_telegram_id=user_telegram_id,
        due_date=due_date,
        event=event,
        comment=comment,
        deposit_document=deposit_document,
        status="pending",
    )
    session.add(rental_request)
    await session.flush()  # чтобы получить rental_request.id

    for item in items_list:
        session.add(
            RentalRequestItem(
                rental_request_id=rental_request.id,
                gear_id=int(item["gear_id"]),
                qty_requested=int(item["qty_requested"]),
            )
        )

    return rental_request


async def update_rental_request_items(
    *,
    session: AsyncSession,
    rental_request: RentalRequest,
    items: Iterable[dict],
) -> None:
    """Обновляет состав заявки в режиме pending."""

    items_list = list(items)
    if not items_list:
        raise ValueError("Заявка должна содержать хотя бы одну позицию")

    gear_ids = {int(item["gear_id"]) for item in items_list}
    gear_result = await session.execute(select(Gear).where(Gear.id.in_(gear_ids)))
    gears = {g.id: g for g in gear_result.scalars().all()}
    missing = gear_ids - set(gears.keys())
    if missing:
        raise ValueError("Снаряжение не найдено")

    await session.execute(
        RentalRequestItem.__table__.delete().where(
            RentalRequestItem.rental_request_id == rental_request.id
        )
    )

    for item in items_list:
        session.add(
            RentalRequestItem(
                rental_request_id=rental_request.id,
                gear_id=int(item["gear_id"]),
                qty_requested=int(item["qty_requested"]),
            )
        )


async def approve_rental_request(
    *,
    session: AsyncSession,
    rental_request: RentalRequest,
    manager_id: int,
    manager_comment: str | None,
) -> Rental:
    """
    Принимает заявку: проверяет наличие инвентаря, уменьшает available_count
    и создает Rental(ы) (по текущей модели - по одной строке аренды на gear_id).
    """

    items_result = await session.execute(
        select(RentalRequestItem).where(
            RentalRequestItem.rental_request_id == rental_request.id
        )
    )
    request_items = items_result.scalars().all()

    if not request_items:
        raise ValueError("Заявка не содержит позиций")

    gear_ids = [ri.gear_id for ri in request_items]
    gear_result = await session.execute(
        select(Gear).where(Gear.id.in_(gear_ids))
    )
    gears = {g.id: g for g in gear_result.scalars().all()}

    for ri in request_items:
        gear = gears.get(ri.gear_id)
        if gear is None:
            raise ValueError("Снаряжение не найдено")
        if ri.qty_requested > gear.available_count:
            raise ValueError(
                f"Недостаточно снаряжения: gear_id={ri.gear_id}, доступно={gear.available_count}, нужно={ri.qty_requested}"
            )

    created_rentals: list[Rental] = []
    for ri in request_items:
        gear = gears[ri.gear_id]
        gear.available_count -= ri.qty_requested

        rental = Rental(
            user_telegram_id=rental_request.user_telegram_id,
            issue_manager_tg_id=manager_id,
            accept_manager_tg_id=None,
            gear_id=ri.gear_id,
            due_date=rental_request.due_date,
            return_date=None,
            quantity=ri.qty_requested,
            event=rental_request.event,
            comment=rental_request.comment,
        )
        session.add(rental)
        created_rentals.append(rental)

    rental_request.status = "approved"
    rental_request.decision_manager_tg_id = manager_id
    rental_request.decision_comment = manager_comment

    return created_rentals[0]


async def reject_rental_request(
    *,
    session: AsyncSession,
    rental_request: RentalRequest,
    manager_id: int,
    manager_comment: str | None,
) -> None:
    rental_request.status = "rejected"
    rental_request.decision_manager_tg_id = manager_id
    rental_request.decision_comment = manager_comment
