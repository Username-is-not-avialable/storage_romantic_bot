"""Бизнес-логика аренды: выдача (ISSUE) и возвраты (RETURN_PARTIAL / RETURN_FINAL)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.database import (
    Gear,
    Rental,
    RentalEvent,
    RentalEventItem,
    RentalItem,
)

RENTAL_ISSUE = "ISSUE"
RENTAL_RETURN_PARTIAL = "RETURN_PARTIAL"
RENTAL_RETURN_FINAL = "RETURN_FINAL"

_RETURN_EVENT_TYPES = (RENTAL_RETURN_PARTIAL, RENTAL_RETURN_FINAL)


async def get_rental_by_id(rental_id: int, session: AsyncSession) -> Rental | None:
    result = await session.execute(
        select(Rental)
        .options(selectinload(Rental.items))
        .where(Rental.id == rental_id)
    )
    return result.scalars().first()


def _merge_qty_by_gear(lines: Iterable[tuple[int, int]]) -> dict[int, int]:
    out: dict[int, int] = {}
    for gear_id, qty in lines:
        if qty <= 0:
            raise ValueError("Количество должно быть больше нуля")
        out[gear_id] = out.get(gear_id, 0) + qty
    return out


async def total_returned_by_gear(session: AsyncSession, rental_id: int) -> dict[int, int]:
    q = (
        select(RentalEventItem.gear_id, func.coalesce(func.sum(RentalEventItem.qty_returned), 0))
        .join(RentalEvent, RentalEvent.id == RentalEventItem.rental_event_id)
        .where(
            RentalEvent.rental_id == rental_id,
            RentalEvent.type.in_(_RETURN_EVENT_TYPES),
        )
        .group_by(RentalEventItem.gear_id)
    )
    rows = (await session.execute(q)).all()
    return {int(g): int(s) for g, s in rows}


async def outstanding_by_gear(session: AsyncSession, rental: Rental) -> dict[int, int]:
    items = (
        await session.execute(select(RentalItem).where(RentalItem.rental_id == rental.id))
    ).scalars().all()
    returned = await total_returned_by_gear(session, rental.id)
    out: dict[int, int] = {}
    for ri in items:
        r = returned.get(ri.gear_id, 0)
        out[ri.gear_id] = ri.qty_issued - r
        if out[ri.gear_id] < 0:
            raise ValueError("Инвариант аренды нарушен: возвращено больше выданного")
    return out


async def issue_rental(
    *,
    session: AsyncSession,
    user_id: int,
    issue_manager_id: int,
    due_date: date,
    event: str,
    comment: str | None,
    lines: list[tuple[int, int]],
    issue_date: date | None = None,
    fee_status_snapshot: str | None = None,
) -> Rental:
    """
    Создаёт аренду: шапку, rental_items, событие ISSUE (без rental_event_items),
    уменьшает available_count по каждой позиции.
    lines: список (gear_id, qty).
    """
    merged = _merge_qty_by_gear(lines)
    if not merged:
        raise ValueError("Должна быть хотя бы одна позиция снаряжения")

    gear_ids = list(merged.keys())
    gear_result = await session.execute(select(Gear).where(Gear.id.in_(gear_ids)))
    gears = {g.id: g for g in gear_result.scalars().all()}
    if set(gears.keys()) != set(gear_ids):
        raise ValueError("Снаряжение не найдено")

    for gid, need in merged.items():
        g = gears[gid]
        if need > g.available_count:
            raise ValueError(
                f"Недостаточно снаряжения: gear_id={gid}, доступно={g.available_count}, нужно={need}"
            )

    eff_issue_date = issue_date or datetime.now(timezone.utc).date()
    now = datetime.now(timezone.utc)

    rental = Rental(
        user_id=user_id,
        issue_manager_id=issue_manager_id,
        issue_date=eff_issue_date,
        due_date=due_date,
        event=event,
        comment=comment,
        status="active",
        closed_at=None,
    )
    session.add(rental)
    await session.flush()

    for gid, qty in merged.items():
        session.add(
            RentalItem(
                rental_id=rental.id,
                gear_id=gid,
                qty_issued=qty,
            )
        )
        g = gears[gid]
        g.available_count -= qty

    session.add(
        RentalEvent(
            rental_id=rental.id,
            type=RENTAL_ISSUE,
            created_at=now,
            manager_id=issue_manager_id,
            comment=None,
            fee_status_snapshot=fee_status_snapshot,
        )
    )

    await session.flush()
    await session.refresh(rental)
    return rental


async def return_rental(
    *,
    session: AsyncSession,
    rental_id: int,
    manager_id: int,
    lines: list[tuple[int, int]],
    fee_status_snapshot: str | None = None,
    comment: str | None = None,
) -> Rental:
    """
    Фиксирует возврат: событие RETURN_PARTIAL или RETURN_FINAL + rental_event_items,
    увеличивает available_count. Закрывает аренду при полном возврате всех позиций.
    """
    merged = _merge_qty_by_gear(lines)
    if not merged:
        raise ValueError("Укажите хотя бы одну позицию возврата")

    result = await session.execute(
        select(Rental)
        .options(selectinload(Rental.items))
        .where(Rental.id == rental_id)
    )
    rental = result.scalars().first()
    if rental is None:
        raise ValueError("Аренда не найдена")
    if rental.status != "active":
        raise ValueError("Аренда уже закрыта")

    outstanding = await outstanding_by_gear(session, rental)

    for gid, want_back in merged.items():
        if gid not in outstanding:
            raise ValueError(f"Позиция gear_id={gid} не входит в эту аренду")
        if want_back > outstanding[gid]:
            raise ValueError(
                f"Нельзя вернуть больше остатка по позиции gear_id={gid}: "
                f"запрошено {want_back}, осталось {outstanding[gid]}"
            )

    for gid in merged:
        gear_row = await session.get(Gear, gid)
        if gear_row is None:
            raise ValueError("Снаряжение не найдено")

    now = datetime.now(timezone.utc)

    remaining_after: dict[int, int] = dict(outstanding)
    for gid, qty in merged.items():
        remaining_after[gid] -= qty

    all_zero = all(v == 0 for v in remaining_after.values())
    event_type = RENTAL_RETURN_FINAL if all_zero else RENTAL_RETURN_PARTIAL

    ev = RentalEvent(
        rental_id=rental.id,
        type=event_type,
        created_at=now,
        manager_id=manager_id,
        comment=comment,
        fee_status_snapshot=fee_status_snapshot,
    )
    session.add(ev)
    await session.flush()

    for gid, qty in merged.items():
        session.add(
            RentalEventItem(
                rental_event_id=ev.id,
                gear_id=gid,
                qty_returned=qty,
                damage_notes=None,
            )
        )
        gr = await session.get(Gear, gid)
        assert gr is not None
        gr.available_count += qty

    if event_type == RENTAL_RETURN_FINAL:
        rental.status = "closed"
        rental.closed_at = now

    await session.flush()
    await session.refresh(rental)
    return rental
