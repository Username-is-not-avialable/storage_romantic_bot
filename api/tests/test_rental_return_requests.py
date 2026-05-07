from datetime import date

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import Gear, Rental, RentalEvent, User
from api.main import app
from api.services.auth import hash_password
from api.services.rentals import issue_rental


async def _seed_default_users(session: AsyncSession) -> tuple[User, User, User]:
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
            User(
                email="admin@example.com",
                password_hash=hash_password("adminpass"),
                full_name="Admin",
                phone="+300",
                role="admin",
            ),
        ]
    )
    await session.commit()
    m_res = await session.execute(select(User).where(User.email == "member@example.com"))
    g_res = await session.execute(select(User).where(User.email == "manager@example.com"))
    a_res = await session.execute(select(User).where(User.email == "admin@example.com"))
    return m_res.scalars().first(), g_res.scalars().first(), a_res.scalars().first()


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
async def test_return_request_create_approve_closes_rental(test_db_session: AsyncSession):
    member, manager, _ = await _seed_default_users(test_db_session)
    gear = await _seed_gear(test_db_session, name="RR Tent", total=10, available=10)

    rental = await issue_rental(
        session=test_db_session,
        user_id=member.id,
        issue_manager_id=manager.id,
        due_date=date(2026, 6, 1),
        event="Hike",
        comment=None,
        lines=[(gear.id, 2)],
    )
    await test_db_session.commit()
    await test_db_session.refresh(rental)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        assert (
            await ac.post(
                "/api/auth/login",
                json={"email": "member@example.com", "password": "memberpass"},
            )
        ).status_code == 200

        create = await ac.post(
            "/api/rental-return-requests/",
            json={
                "rental_id": rental.id,
                "items": [{"gear_id": gear.id, "qty_return": 1}],
            },
        )
        assert create.status_code == 200
        rr_id = create.json()["id"]
        assert create.json()["status"] == "pending"

        assert (
            await ac.post(
                "/api/auth/login",
                json={"email": "manager@example.com", "password": "managerpass"},
            )
        ).status_code == 200

        approve = await ac.patch(
            f"/api/manager/rental-return-requests/{rr_id}",
            json={"decision": "approve", "comment": "ok"},
        )
        assert approve.status_code == 200
        assert approve.json()["status"] == "approved"

    g_row = (
        (await test_db_session.execute(select(Gear).where(Gear.id == gear.id))).scalars().first()
    )
    assert g_row.available_count == 9

    r_row = (
        (await test_db_session.execute(select(Rental).where(Rental.id == rental.id)))
        .scalars()
        .first()
    )
    assert r_row.status == "active"

    ev = (
        (
            await test_db_session.execute(
                select(RentalEvent).where(
                    RentalEvent.rental_id == rental.id,
                    RentalEvent.type == "RETURN_PARTIAL",
                )
            )
        )
        .scalars()
        .first()
    )
    assert ev is not None

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac2:
        await ac2.post(
            "/api/auth/login",
            json={"email": "member@example.com", "password": "memberpass"},
        )
        c2 = await ac2.post(
            "/api/rental-return-requests/",
            json={"rental_id": rental.id, "items": [{"gear_id": gear.id, "qty_return": 1}]},
        )
        assert c2.status_code == 200
        rr2 = c2.json()["id"]

        await ac2.post(
            "/api/auth/login",
            json={"email": "manager@example.com", "password": "managerpass"},
        )
        ap2 = await ac2.patch(
            f"/api/manager/rental-return-requests/{rr2}",
            json={"decision": "approve", "comment": "done"},
        )
        assert ap2.status_code == 200

    r_final = (
        (await test_db_session.execute(select(Rental).where(Rental.id == rental.id)))
        .scalars()
        .first()
    )
    assert r_final.status == "closed"


@pytest.mark.asyncio
async def test_manager_can_create_return_request_for_own_rental(test_db_session: AsyncSession):
    _, manager, admin = await _seed_default_users(test_db_session)
    gear = await _seed_gear(test_db_session, name="Mgr RR Own", total=10, available=10)

    rental = await issue_rental(
        session=test_db_session,
        user_id=manager.id,
        issue_manager_id=admin.id,
        due_date=date(2026, 6, 15),
        event="Mgr borrow",
        comment=None,
        lines=[(gear.id, 1)],
    )
    await test_db_session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/auth/login",
            json={"email": "manager@example.com", "password": "managerpass"},
        )
        create = await ac.post(
            "/api/rental-return-requests/",
            json={
                "rental_id": rental.id,
                "items": [{"gear_id": gear.id, "qty_return": 1}],
            },
        )
        assert create.status_code == 200
        assert create.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_return_request_reject_does_not_touch_rental(test_db_session: AsyncSession):
    member, manager, _ = await _seed_default_users(test_db_session)
    gear = await _seed_gear(test_db_session, name="RR Rej", total=5, available=5)

    rental = await issue_rental(
        session=test_db_session,
        user_id=member.id,
        issue_manager_id=manager.id,
        due_date=date(2026, 6, 1),
        event="Hike",
        comment=None,
        lines=[(gear.id, 1)],
    )
    await test_db_session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/auth/login",
            json={"email": "member@example.com", "password": "memberpass"},
        )
        cr = await ac.post(
            "/api/rental-return-requests/",
            json={"rental_id": rental.id, "items": [{"gear_id": gear.id, "qty_return": 1}]},
        )
        assert cr.status_code == 200
        rid = cr.json()["id"]

        await ac.post(
            "/api/auth/login",
            json={"email": "manager@example.com", "password": "managerpass"},
        )
        rj = await ac.patch(
            f"/api/manager/rental-return-requests/{rid}",
            json={"decision": "reject", "comment": "busy"},
        )
        assert rj.status_code == 200
        assert rj.json()["status"] == "rejected"

    g_row = (
        (await test_db_session.execute(select(Gear).where(Gear.id == gear.id))).scalars().first()
    )
    assert g_row.available_count == 4

    ev_cnt = (
        (
            await test_db_session.execute(
                select(RentalEvent).where(
                    RentalEvent.rental_id == rental.id,
                    RentalEvent.type.in_(["RETURN_PARTIAL", "RETURN_FINAL"]),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(ev_cnt) == 0


@pytest.mark.asyncio
async def test_second_pending_for_same_rental_rejected(test_db_session: AsyncSession):
    member, manager, _ = await _seed_default_users(test_db_session)
    gear = await _seed_gear(test_db_session, name="RR Dup", total=5, available=5)

    rental = await issue_rental(
        session=test_db_session,
        user_id=member.id,
        issue_manager_id=manager.id,
        due_date=date(2026, 6, 1),
        event="Hike",
        comment=None,
        lines=[(gear.id, 2)],
    )
    await test_db_session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/auth/login",
            json={"email": "member@example.com", "password": "memberpass"},
        )
        first = await ac.post(
            "/api/rental-return-requests/",
            json={"rental_id": rental.id, "items": [{"gear_id": gear.id, "qty_return": 1}]},
        )
        assert first.status_code == 200

        second = await ac.post(
            "/api/rental-return-requests/",
            json={"rental_id": rental.id, "items": [{"gear_id": gear.id, "qty_return": 1}]},
        )
        assert second.status_code == 400


@pytest.mark.asyncio
async def test_manager_decide_forbidden_for_member(test_db_session: AsyncSession):
    await _seed_default_users(test_db_session)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/auth/login",
            json={"email": "member@example.com", "password": "memberpass"},
        )
        r = await ac.patch(
            "/api/manager/rental-return-requests/999",
            json={"decision": "reject", "comment": "x"},
        )
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_target_manager_only_that_manager_or_admin(test_db_session: AsyncSession):
    member, mgr_target, _ = await _seed_default_users(test_db_session)

    test_db_session.add(
        User(
            email="manager_other@example.com",
            password_hash=hash_password("otherpass"),
            full_name="Manager Other",
            phone="+250",
            role="manager",
        )
    )
    await test_db_session.commit()
    other_res = await test_db_session.execute(
        select(User).where(User.email == "manager_other@example.com")
    )
    assert other_res.scalars().first() is not None

    gear = await _seed_gear(test_db_session, name="RR Target", total=5, available=5)

    rental = await issue_rental(
        session=test_db_session,
        user_id=member.id,
        issue_manager_id=mgr_target.id,
        due_date=date(2026, 6, 1),
        event="Hike",
        comment=None,
        lines=[(gear.id, 1)],
    )
    await test_db_session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/auth/login",
            json={"email": "member@example.com", "password": "memberpass"},
        )
        cr = await ac.post(
            "/api/rental-return-requests/",
            json={
                "rental_id": rental.id,
                "target_manager_id": mgr_target.id,
                "items": [{"gear_id": gear.id, "qty_return": 1}],
            },
        )
        assert cr.status_code == 200
        rr_id = cr.json()["id"]

        assert (
            await ac.post(
                "/api/auth/login",
                json={"email": "manager_other@example.com", "password": "otherpass"},
            )
        ).status_code == 200

        bad = await ac.patch(
            f"/api/manager/rental-return-requests/{rr_id}",
            json={"decision": "approve", "comment": "wrong mgr"},
        )
        assert bad.status_code == 400

        await ac.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "adminpass"},
        )
        ok = await ac.patch(
            f"/api/manager/rental-return-requests/{rr_id}",
            json={"decision": "approve", "comment": "admin ok"},
        )
        assert ok.status_code == 200
        assert ok.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_return_request_list_mine_and_manager_queue(test_db_session: AsyncSession):
    member, manager, _ = await _seed_default_users(test_db_session)
    gear = await _seed_gear(test_db_session, name="RR List", total=10, available=10)

    rental = await issue_rental(
        session=test_db_session,
        user_id=member.id,
        issue_manager_id=manager.id,
        due_date=date(2026, 6, 1),
        event="Hike",
        comment=None,
        lines=[(gear.id, 2)],
    )
    await test_db_session.commit()
    await test_db_session.refresh(rental)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/auth/login",
            json={"email": "member@example.com", "password": "memberpass"},
        )
        create = await ac.post(
            "/api/rental-return-requests/",
            json={
                "rental_id": rental.id,
                "items": [{"gear_id": gear.id, "qty_return": 1}],
            },
        )
        assert create.status_code == 200
        rr_id = create.json()["id"]

        mine = await ac.get("/api/rental-return-requests/?status=pending")
        assert mine.status_code == 200
        assert len(mine.json()["requests"]) == 1
        assert mine.json()["requests"][0]["id"] == rr_id

        await ac.post(
            "/api/auth/login",
            json={"email": "manager@example.com", "password": "managerpass"},
        )
        queue = await ac.get("/api/manager/rental-return-requests/?status=pending")
        assert queue.status_code == 200
        ids = {r["id"] for r in queue.json()["requests"]}
        assert rr_id in ids


@pytest.mark.asyncio
async def test_manager_return_request_queue_forbidden_for_member(test_db_session: AsyncSession):
    await _seed_default_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/auth/login",
            json={"email": "member@example.com", "password": "memberpass"},
        )
        r = await ac.get("/api/manager/rental-return-requests/")
        assert r.status_code == 403
