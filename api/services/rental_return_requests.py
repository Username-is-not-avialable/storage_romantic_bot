"""Заявки на возврат снаряжения по активной аренде (делегирование в return_rental при approve)."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import (
    Rental,
    RentalReturnRequest,
    RentalReturnRequestItem,
    User,
)
from api.services.rentals import get_rental_by_id, outstanding_by_gear, return_rental


async def get_return_request_by_id(
    return_request_id: int,
    session: AsyncSession,
) -> RentalReturnRequest | None:
    result = await session.execute(
        select(RentalReturnRequest).where(RentalReturnRequest.id == return_request_id)
    )
    return result.scalars().first()


def _merge_qty_by_gear(lines: Iterable[tuple[int, int]]) -> dict[int, int]:
    out: dict[int, int] = {}
    for gear_id, qty in lines:
        if qty <= 0:
            raise ValueError("Количество должно быть больше нуля")
        out[gear_id] = out.get(gear_id, 0) + qty
    return out


async def _validate_no_pending_for_rental(
    session: AsyncSession, rental_id: int
) -> None:
    q = select(RentalReturnRequest.id).where(
        RentalReturnRequest.rental_id == rental_id,
        RentalReturnRequest.status == "pending",
    )
    row = (await session.execute(q)).first()
    if row is not None:
        raise ValueError(
            "По этой аренде уже есть заявка на возврат в статусе «ожидает решения»"
        )


async def _validate_target_manager(session: AsyncSession, target_manager_id: int) -> None:
    u = await session.get(User, target_manager_id)
    if u is None:
        raise ValueError("Целевой менеджер не найден")
    if u.role not in ("manager", "admin"):
        raise ValueError("Целевой пользователь должен быть завснаром или администратором")


def _assert_manager_can_decide(
    req: RentalReturnRequest,
    manager: User,
) -> None:
    if req.target_manager_id is None:
        return
    if manager.role == "admin":
        return
    if manager.id != req.target_manager_id:
        raise ValueError("Эта заявка адресована другому менеджеру")


async def create_rental_return_request(
    *,
    session: AsyncSession,
    user_id: int,
    rental_id: int,
    items: Iterable[dict],
    target_manager_id: int | None,
) -> RentalReturnRequest:
    """
    Создаёт заявку (pending). items: {"gear_id": int, "qty_return": int}.
    Не более одной pending-заявки на одну аренду.
    """
    items_list = list(items)
    if not items_list:
        raise ValueError("Укажите хотя бы одну позицию возврата")

    merged = _merge_qty_by_gear(
        (int(x["gear_id"]), int(x["qty_return"])) for x in items_list
    )

    rental = await get_rental_by_id(rental_id, session)
    if rental is None:
        raise ValueError("Аренда не найдена")
    if rental.user_id != user_id:
        raise ValueError("Нельзя оформить возврат по чужой аренде")
    if rental.status != "active":
        raise ValueError("Возможен возврат только по активной аренде")

    await _validate_no_pending_for_rental(session, rental_id)

    if target_manager_id is not None:
        await _validate_target_manager(session, target_manager_id)

    outstanding = await outstanding_by_gear(session, rental)
    for gid, qty in merged.items():
        if gid not in outstanding:
            raise ValueError(f"Позиция gear_id={gid} не входит в эту аренду")
        if qty > outstanding[gid]:
            raise ValueError(
                f"Нельзя вернуть больше остатка по позиции gear_id={gid}: "
                f"запрошено {qty}, осталось {outstanding[gid]}"
            )

    req = RentalReturnRequest(
        user_id=user_id,
        rental_id=rental_id,
        target_manager_id=target_manager_id,
        status="pending",
    )
    session.add(req)
    await session.flush()

    for gid, qty in merged.items():
        session.add(
            RentalReturnRequestItem(
                rental_return_request_id=req.id,
                gear_id=gid,
                qty_return=qty,
            )
        )

    return req


async def approve_rental_return_request(
    *,
    session: AsyncSession,
    req: RentalReturnRequest,
    manager: User,
    manager_comment: str | None,
) -> Rental:
    """Принимает заявку: в той же транзакции вызывает return_rental."""
    items_result = await session.execute(
        select(RentalReturnRequestItem).where(
            RentalReturnRequestItem.rental_return_request_id == req.id
        )
    )
    request_items = items_result.scalars().all()
    if not request_items:
        raise ValueError("Заявка не содержит позиций")

    _assert_manager_can_decide(req, manager)

    lines = [(ri.gear_id, ri.qty_return) for ri in request_items]

    rental = await return_rental(
        session=session,
        rental_id=req.rental_id,
        manager_id=manager.id,
        lines=lines,
        fee_status_snapshot=None,
        comment=manager_comment,
    )

    req.status = "approved"
    req.decision_manager_id = manager.id
    req.decision_comment = manager_comment

    return rental


async def reject_rental_return_request(
    *,
    session: AsyncSession,
    req: RentalReturnRequest,
    manager: User,
    manager_comment: str | None,
) -> None:
    _assert_manager_can_decide(req, manager)

    req.status = "rejected"
    req.decision_manager_id = manager.id
    req.decision_comment = manager_comment
