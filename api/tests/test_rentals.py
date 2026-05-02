import pytest
import httpx
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import Gear, Rental, RentalEvent, RentalItem, User
from api.main import app
from api.services.auth import hash_password


async def _seed_users(session: AsyncSession) -> None:
    session.add_all(
        [
            User(
                email="member@example.com",
                password_hash=hash_password("memberpass"),
                full_name="Member",
                phone="+100",
                role="member",
            ),
            User(
                email="manager@example.com",
                password_hash=hash_password("managerpass"),
                full_name="Manager",
                phone="+200",
                role="manager",
            ),
        ]
    )
    await session.commit()


async def _seed_gear(session: AsyncSession, name: str, total: int, available: int) -> Gear:
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
async def test_issue_two_gear_positions(test_db_session: AsyncSession):
    await _seed_users(test_db_session)
    g1 = await _seed_gear(test_db_session, name="A", total=10, available=5)
    g2 = await _seed_gear(test_db_session, name="B", total=10, available=4)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        login = await ac.post("/api/auth/login", json={"email": "manager@example.com", "password": "managerpass"})
        assert login.status_code == 200
        resp = await ac.post(
            "/api/rentals/issue",
            json={
                "user_id": 1,
                "issue_manager_id": 2,
                "due_date": "15.06.2026",
                "event": "Hike",
                "comment": None,
                "items": [
                    {"gear_id": g1.id, "qty": 2},
                    {"gear_id": g2.id, "qty": 3},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert len(data["items"]) == 2
        assert {i["qty_issued"] for i in data["items"]} == {2, 3}

    r1 = await test_db_session.get(Gear, g1.id)
    r2 = await test_db_session.get(Gear, g2.id)
    assert r1.available_count == 3
    assert r2.available_count == 1


@pytest.mark.asyncio
async def test_partial_then_final_return(test_db_session: AsyncSession):
    await _seed_users(test_db_session)
    g = await _seed_gear(test_db_session, name="Pole", total=10, available=5)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        login = await ac.post("/api/auth/login", json={"email": "manager@example.com", "password": "managerpass"})
        assert login.status_code == 200
        issue = await ac.post(
            "/api/rentals/issue",
            json={
                "user_id": 1,
                "issue_manager_id": 2,
                "due_date": "15.06.2026",
                "event": "Hike",
                "items": [{"gear_id": g.id, "qty": 4}],
            },
        )
        assert issue.status_code == 200
        rental_id = issue.json()["id"]

        part = await ac.patch(
            f"/api/rentals/{rental_id}/return",
            json={
                "manager_id": 2,
                "items": [{"gear_id": g.id, "quantity": 1}],
            },
        )
        assert part.status_code == 200
        assert part.json()["status"] == "active"
        assert part.json()["items"][0]["qty_outstanding"] == 3

        fin = await ac.patch(
            f"/api/rentals/{rental_id}/return",
            json={
                "manager_id": 2,
                "items": [{"gear_id": g.id, "quantity": 3}],
            },
        )
        assert fin.status_code == 200
        assert fin.json()["status"] == "closed"
        assert fin.json()["closed_at"] is not None

    gear_after = await test_db_session.get(Gear, g.id)
    assert gear_after.available_count == 5

    ev_res = await test_db_session.execute(
        select(RentalEvent).where(RentalEvent.rental_id == rental_id).order_by(RentalEvent.id)
    )
    evs = ev_res.scalars().all()
    types = [e.type for e in evs]
    assert "ISSUE" in types
    assert "RETURN_PARTIAL" in types
    assert "RETURN_FINAL" in types


@pytest.mark.asyncio
async def test_return_exceeds_outstanding_400(test_db_session: AsyncSession):
    await _seed_users(test_db_session)
    g = await _seed_gear(test_db_session, name="X", total=10, available=3)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        login = await ac.post("/api/auth/login", json={"email": "manager@example.com", "password": "managerpass"})
        assert login.status_code == 200
        issue = await ac.post(
            "/api/rentals/issue",
            json={
                "user_id": 1,
                "issue_manager_id": 2,
                "due_date": "15.06.2026",
                "event": "Hike",
                "items": [{"gear_id": g.id, "qty": 2}],
            },
        )
        rental_id = issue.json()["id"]

        bad = await ac.patch(
            f"/api/rentals/{rental_id}/return",
            json={
                "manager_id": 2,
                "items": [{"gear_id": g.id, "quantity": 5}],
            },
        )
        assert bad.status_code == 400


@pytest.mark.asyncio
async def test_get_debtors_returns_only_overdue_active_rentals(test_db_session: AsyncSession):
    await _seed_users(test_db_session)
    g = await _seed_gear(test_db_session, name="DebtorGear", total=10, available=10)

    old_due = (date.today() - timedelta(days=2)).isoformat()
    future_due = (date.today() + timedelta(days=5)).isoformat()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        login = await ac.post("/api/auth/login", json={"email": "manager@example.com", "password": "managerpass"})
        assert login.status_code == 200
        overdue_resp = await ac.post(
            "/api/rentals/issue",
            json={
                "user_id": 1,
                "issue_manager_id": 2,
                "due_date": old_due,
                "event": "Overdue trip",
                "items": [{"gear_id": g.id, "qty": 1}],
            },
        )
        assert overdue_resp.status_code == 200
        overdue_id = overdue_resp.json()["id"]

        in_time_resp = await ac.post(
            "/api/rentals/issue",
            json={
                "user_id": 1,
                "issue_manager_id": 2,
                "due_date": future_due,
                "event": "Future trip",
                "items": [{"gear_id": g.id, "qty": 1}],
            },
        )
        assert in_time_resp.status_code == 200

        debtors_resp = await ac.get("/api/rentals/debtors")
        assert debtors_resp.status_code == 200
        debtors = debtors_resp.json()["rentals"]
        assert len(debtors) == 1
        assert debtors[0]["id"] == overdue_id
        assert debtors[0]["status"] == "active"
