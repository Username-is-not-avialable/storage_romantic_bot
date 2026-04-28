import pytest
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import Gear, Rental, RentalEvent, RentalItem, RentalRequest
from api.main import app
from api.database import User


async def _seed_users(session: AsyncSession) -> None:
    session.add_all(
        [
            User(id_telegram=1, full_name="Member", phone="+100", role="member"),
            User(id_telegram=2, full_name="Manager", phone="+200", role="manager"),
            User(id_telegram=3, full_name="Admin", phone="+300", role="admin"),
        ]
    )
    await session.commit()


async def _seed_gear(session: AsyncSession, *, name: str, total: int, available: int) -> Gear:
    gear = Gear(
        name=name,
        total_quantity=total,
        available_count=available,
        description="t",
    )
    session.add(gear)
    await session.commit()
    await session.refresh(gear)
    return gear


@pytest.mark.asyncio
async def test_pending_update_then_reject(test_db_session: AsyncSession):
    await _seed_users(test_db_session)
    gear = await _seed_gear(test_db_session, name="Tent", total=10, available=10)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        create_resp = await ac.post(
            "/api/rental-requests/?id_telegram=1",
            json={
                "due_date": "02.04.2026",
                "event": "Trip",
                "comment": "c1",
                "deposit_document": "doc.pdf",
                "items": [{"gear_id": gear.id, "qty_requested": 2}],
            },
        )
        assert create_resp.status_code == 200
        data = create_resp.json()
        assert data["status"] == "pending"
        request_id = data["id"]

        update_resp = await ac.patch(
            f"/api/rental-requests/{request_id}?id_telegram=1",
            json={
                "comment": "c2",
                "items": [{"gear_id": gear.id, "qty_requested": 3}],
            },
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["status"] == "pending"

        reject_resp = await ac.patch(
            f"/api/manager/rental-requests/{request_id}?id_telegram=2",
            json={"decision": "reject", "comment": "nope"},
        )
        assert reject_resp.status_code == 200
        rejected = reject_resp.json()
        assert rejected["status"] == "rejected"
        assert rejected["decision_comment"] == "nope"

    req_res = await test_db_session.execute(
        select(RentalRequest).where(RentalRequest.id == request_id)
    )
    req_row = req_res.scalars().first()
    assert req_row is not None
    assert req_row.status == "rejected"


@pytest.mark.asyncio
async def test_pending_approve_creates_rentals(test_db_session: AsyncSession):
    await _seed_users(test_db_session)
    gear = await _seed_gear(test_db_session, name="Tent2", total=10, available=10)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        create_resp = await ac.post(
            "/api/rental-requests/?id_telegram=1",
            json={
                "due_date": "02.04.2026",
                "event": "Trip",
                "comment": "c1",
                "deposit_document": "doc.pdf",
                "items": [{"gear_id": gear.id, "qty_requested": 2}],
            },
        )
        assert create_resp.status_code == 200
        request_id = create_resp.json()["id"]

        approve_resp = await ac.patch(
            f"/api/manager/rental-requests/{request_id}?id_telegram=2",
            json={"decision": "approve", "comment": "ok"},
        )
        assert approve_resp.status_code == 200
        approved = approve_resp.json()
        assert approved["status"] == "approved"
        assert approved["decision_comment"] == "ok"

    # Проверяем инвентарь
    gear_res = await test_db_session.execute(select(Gear).where(Gear.id == gear.id))
    gear_after = gear_res.scalars().first()
    assert gear_after.available_count == 8

    rentals_res = await test_db_session.execute(
        select(Rental).where(Rental.user_telegram_id == 1)
    )
    rentals = rentals_res.scalars().all()
    assert len(rentals) == 1
    r = rentals[0]
    assert r.status == "active"

    items_res = await test_db_session.execute(
        select(RentalItem).where(RentalItem.rental_id == r.id)
    )
    items = items_res.scalars().all()
    assert len(items) == 1
    assert items[0].qty_issued == 2
    assert items[0].gear_id == gear.id

    ev_res = await test_db_session.execute(
        select(RentalEvent).where(
            RentalEvent.rental_id == r.id,
            RentalEvent.type == "ISSUE",
        )
    )
    assert ev_res.scalars().first() is not None

    req_res = await test_db_session.execute(
        select(RentalRequest).where(RentalRequest.id == request_id)
    )
    req_row = req_res.scalars().first()
    assert req_row is not None
    assert req_row.status == "approved"


@pytest.mark.asyncio
async def test_approve_fails_when_insufficient_inventory(test_db_session: AsyncSession):
    await _seed_users(test_db_session)
    gear = await _seed_gear(test_db_session, name="Tent3", total=10, available=1)
    gear_id = gear.id

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        create_resp = await ac.post(
            "/api/rental-requests/?id_telegram=1",
            json={
                "due_date": "02.04.2026",
                "event": "Trip",
                "items": [{"gear_id": gear_id, "qty_requested": 2}],
            },
        )
        assert create_resp.status_code == 200
        request_id = create_resp.json()["id"]

        approve_resp = await ac.patch(
            f"/api/manager/rental-requests/{request_id}?id_telegram=2",
            json={"decision": "approve", "comment": "ok"},
        )
        assert approve_resp.status_code == 400

    # Инвентарь не должен измениться
    gear_res = await test_db_session.execute(select(Gear).where(Gear.id == gear_id))
    gear_after = gear_res.scalars().first()
    assert gear_after.available_count == 1

    req_res = await test_db_session.execute(
        select(RentalRequest).where(RentalRequest.id == request_id)
    )
    req_row = req_res.scalars().first()
    assert req_row is not None
    assert req_row.status == "pending"
