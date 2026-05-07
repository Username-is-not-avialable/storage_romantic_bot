from __future__ import annotations

from typing import Iterable

from datetime import date

from sqlalchemy import Select, asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import Gear, Rental, RentalRequest, RentalRequestItem, User
from api.services.rentals import issue_rental


def _validate_request_items_vs_available(
    items_list: list,
    gears: dict[int, Gear],
) -> None:
    """Проверка, что по каждой позиции суммарно запрошено не больше, чем есть на складе."""

    qty_by_gear: dict[int, int] = {}
    for item in items_list:
        gid = int(item["gear_id"])
        q = int(item["qty_requested"])
        if q <= 0:
            raise ValueError("Количество должно быть больше нуля")
        qty_by_gear[gid] = qty_by_gear.get(gid, 0) + q

    for gid, need in qty_by_gear.items():
        g = gears[gid]
        if need > g.available_count:
            raise ValueError(
                f"Недостаточно снаряжения «{g.name}»: запрошено {need} шт., доступно {g.available_count}"
            )


async def get_rental_request_by_id(
    rental_request_id: int,
    session: AsyncSession,
) -> RentalRequest | None:
    result = await session.execute(
        select(RentalRequest).where(RentalRequest.id == rental_request_id)
    )
    return result.scalars().first()


def build_manager_rental_requests_query(
    *,
    status: str | None,
    user_id: int | None,
    due_date_from: date | None,
    due_date_to: date | None,
    created_from: date | None,
    created_to: date | None,
    sort_order: str,
) -> Select:
    """Строит SQL-запрос очереди заявок с фильтрами и сортировкой."""

    q = select(RentalRequest)

    if status:
        q = q.where(RentalRequest.status == status)
    if user_id is not None:
        q = q.where(RentalRequest.user_id == user_id)
    if due_date_from is not None:
        q = q.where(RentalRequest.due_date >= due_date_from)
    if due_date_to is not None:
        q = q.where(RentalRequest.due_date <= due_date_to)
    if created_from is not None:
        q = q.where(RentalRequest.created_at >= created_from)
    if created_to is not None:
        q = q.where(RentalRequest.created_at < created_to)

    order_fn = asc if sort_order == "asc" else desc
    q = q.order_by(order_fn(RentalRequest.created_at))

    return q


async def assert_valid_rental_target_manager(
    session: AsyncSession,
    target_manager_id: int,
) -> None:
    """Проверяет, что адресат заявки — активный менеджер или администратор."""

    result = await session.execute(select(User).where(User.id == target_manager_id))
    user = result.scalars().first()
    if user is None:
        raise ValueError("Указанный завснар не найден")
    if not user.is_active:
        raise ValueError("Указанный завснар неактивен")
    if user.role not in ("manager", "admin"):
        raise ValueError("Адресат заявки должен иметь роль завснара или администратора")


async def create_rental_request(
    *,
    session: AsyncSession,
    user_id: int,
    due_date,
    event: str,
    comment: str | None,
    deposit_document: str | None,
    target_manager_id: int,
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

    _validate_request_items_vs_available(items_list, gears)

    await assert_valid_rental_target_manager(session, target_manager_id)

    rental_request = RentalRequest(
        user_id=user_id,
        due_date=due_date,
        event=event,
        comment=comment,
        deposit_document=deposit_document,
        target_manager_id=target_manager_id,
        status="pending",
    )
    session.add(rental_request)
    await session.flush()

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

    _validate_request_items_vs_available(items_list, gears)

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
    Принимает заявку: проверяет наличие инвентаря и создаёт одну аренду-документ
    с составом и событием ISSUE.
    """

    items_result = await session.execute(
        select(RentalRequestItem).where(
            RentalRequestItem.rental_request_id == rental_request.id
        )
    )
    request_items = items_result.scalars().all()

    if not request_items:
        raise ValueError("Заявка не содержит позиций")

    lines = [(ri.gear_id, ri.qty_requested) for ri in request_items]

    rental = await issue_rental(
        session=session,
        user_id=rental_request.user_id,
        issue_manager_id=manager_id,
        due_date=rental_request.due_date,
        event=rental_request.event,
        comment=rental_request.comment,
        lines=lines,
        fee_status_snapshot=None,
    )

    rental_request.status = "approved"
    rental_request.decision_manager_id = manager_id
    rental_request.decision_comment = manager_comment

    return rental


async def reject_rental_request(
    *,
    session: AsyncSession,
    rental_request: RentalRequest,
    manager_id: int,
    manager_comment: str | None,
) -> None:
    rental_request.status = "rejected"
    rental_request.decision_manager_id = manager_id
    rental_request.decision_comment = manager_comment
