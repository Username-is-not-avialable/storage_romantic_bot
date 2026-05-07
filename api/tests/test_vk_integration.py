from __future__ import annotations

from datetime import date

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import Gear, User, UserMessengerLink
from api.main import app
from api.services.auth import hash_password
from api.services.rentals import issue_rental

TEST_VK_SECRET = "test-vk-bot-secret"


async def _seed_two_users(session: AsyncSession) -> None:
    session.add_all(
        [
            User(
                email="vk_u1@example.com",
                password_hash=hash_password("pass-one"),
                full_name="User One",
                phone="+1001",
                role="member",
            ),
            User(
                email="vk_u2@example.com",
                password_hash=hash_password("pass-two"),
                full_name="User Two",
                phone="+1002",
                role="member",
            ),
        ]
    )
    await session.commit()


@pytest.mark.asyncio
async def test_request_vk_link_code_requires_session(test_db_session: AsyncSession):
    await _seed_two_users(test_db_session)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/auth/vk-link/request_code")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_integrations_503_when_secret_not_configured(
    test_db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    await _seed_two_users(test_db_session)
    monkeypatch.setenv("VK_BOT_SECRET", "")
    get_settings.cache_clear()

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api/integrations/vk/link-complete",
                json={"code": "x", "vk_user_id": 1},
                headers={"X-VK-Bot-Secret": "any"},
            )
            assert r.status_code == 503
            assert "VK_BOT_SECRET" in r.json().get("detail", "")
    finally:
        monkeypatch.setenv("VK_BOT_SECRET", TEST_VK_SECRET)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_integrations_401_on_bad_secret(test_db_session: AsyncSession):
    await _seed_two_users(test_db_session)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/integrations/vk/link-complete",
            json={"code": "x", "vk_user_id": 1},
            headers={"X-VK-Bot-Secret": "wrong-secret"},
        )
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_request_vk_link_code_complete_me_and_reuse_code(test_db_session: AsyncSession):
    await _seed_two_users(test_db_session)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        login = await ac.post(
            "/api/auth/login",
            json={"email": "vk_u1@example.com", "password": "pass-one"},
        )
        assert login.status_code == 200

        req_code = await ac.post("/api/auth/vk-link/request_code")
        assert req_code.status_code == 200
        payload = req_code.json()
        code = payload["code"]
        assert code

        c1 = await ac.post(
            "/api/integrations/vk/link-complete",
            json={"code": code, "vk_user_id": 77_777},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
        )
        assert c1.status_code == 200
        assert c1.json()["email"] == "vk_u1@example.com"

        me = await ac.get(
            "/api/integrations/vk/me",
            params={"vk_user_id": 77_777},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
        )
        assert me.status_code == 200
        assert me.json()["full_name"] == "User One"

        again = await ac.post(
            "/api/integrations/vk/link-complete",
            json={"code": code, "vk_user_id": 77_777},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
        )
        assert again.status_code == 400


@pytest.mark.asyncio
async def test_complete_conflict_second_site_user_same_vk_id(test_db_session: AsyncSession):
    await _seed_two_users(test_db_session)
    transport = httpx.ASGITransport(app=app)
    vk_id = 88_888

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac1:
        assert (
            await ac1.post(
                "/api/auth/login",
                json={"email": "vk_u1@example.com", "password": "pass-one"},
            )
        ).status_code == 200
        req1 = await ac1.post("/api/auth/vk-link/request_code")
        code1 = req1.json()["code"]
        r_ok = await ac1.post(
            "/api/integrations/vk/link-complete",
            json={"code": code1, "vk_user_id": vk_id},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
        )
        assert r_ok.status_code == 200

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac2:
        assert (
            await ac2.post(
                "/api/auth/login",
                json={"email": "vk_u2@example.com", "password": "pass-two"},
            )
        ).status_code == 200
        req2 = await ac2.post("/api/auth/vk-link/request_code")
        code2 = req2.json()["code"]
        r_conflict = await ac2.post(
            "/api/integrations/vk/link-complete",
            json={"code": code2, "vk_user_id": vk_id},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
        )
        assert r_conflict.status_code == 409
        assert "VK" in r_conflict.json().get("detail", "") or "vk" in r_conflict.json().get("detail", "").lower()

        req3 = await ac2.post("/api/auth/vk-link/request_code")
        code3 = req3.json()["code"]
        r_retry_other_vk = await ac2.post(
            "/api/integrations/vk/link-complete",
            json={"code": code3, "vk_user_id": vk_id + 1},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
        )
        assert r_retry_other_vk.status_code == 200


async def _seed_manager_user_plain(session: AsyncSession, *, email: str) -> User:
    """Активный завснар без привязки VK (как target_manager_id в тестах VK API)."""

    suffix = abs(hash(email)) % 10_000_000
    mgr = User(
        email=email,
        password_hash=hash_password("t"),
        full_name="Plain Manager",
        phone=f"+79{suffix:09d}"[:16],
        role="manager",
    )
    session.add(mgr)
    await session.commit()
    await session.refresh(mgr)
    return mgr


async def _seed_member_with_vk_and_gear(
    session: AsyncSession, *, vk_user_id: int
) -> tuple[User, Gear]:
    """Участник `member` с привязкой VK и одной позицией снаряжения для заявок."""
    user = User(
        email="vk_member_req@example.com",
        password_hash=hash_password("m"),
        full_name="VK Member",
        phone="+1999",
        role="member",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    session.add(
        UserMessengerLink(
            user_id=user.id,
            provider="vk",
            external_user_id=str(vk_user_id),
        )
    )
    gear = Gear(
        name="VkRentalGear",
        total_quantity=10,
        available_count=10,
        description="t",
    )
    session.add(gear)
    await session.commit()
    await session.refresh(gear)
    return user, gear


async def _seed_manager_with_vk(session: AsyncSession, *, vk_user_id: int) -> User:
    mgr = User(
        email="vk_mgr@example.com",
        password_hash=hash_password("mgr"),
        full_name="VK Manager",
        phone="+2999",
        role="manager",
    )
    session.add(mgr)
    await session.commit()
    await session.refresh(mgr)
    session.add(
        UserMessengerLink(
            user_id=mgr.id,
            provider="vk",
            external_user_id=str(vk_user_id),
        )
    )
    await session.commit()
    return mgr


async def _seed_manager_with_vk_and_gear(
    session: AsyncSession, *, vk_user_id: int
) -> tuple[User, Gear]:
    """Менеджер с привязкой VK и позицией снаряжения для заявок от имени менеджера."""
    user = User(
        email="vk_mgr_rental_req@example.com",
        password_hash=hash_password("mgr"),
        full_name="VK Manager Rental",
        phone="+2998",
        role="manager",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    session.add(
        UserMessengerLink(
            user_id=user.id,
            provider="vk",
            external_user_id=str(vk_user_id),
        )
    )
    gear = Gear(
        name="VkMgrRentalGear",
        total_quantity=10,
        available_count=10,
        description="t",
    )
    session.add(gear)
    await session.commit()
    await session.refresh(gear)
    return user, gear


@pytest.mark.asyncio
async def test_vk_create_rental_request_success(test_db_session):
    vk_id = 600_001
    _, gear = await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=vk_id)
    target = await _seed_manager_user_plain(test_db_session, email="vk_target_ok@example.com")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/integrations/vk/rental-requests",
            params={"vk_user_id": vk_id},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={
                "due_date": "02.04.2026",
                "event": "TripVK",
                "comment": "via bot",
                "deposit_document": "d.pdf",
                "target_manager_id": target.id,
                "items": [{"gear_id": gear.id, "qty_requested": 1}],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "pending"
        assert data["event"] == "TripVK"
        assert len(data["items"]) == 1
        assert data["items"][0]["gear_id"] == gear.id


@pytest.mark.asyncio
async def test_vk_manager_can_create_rental_request(test_db_session):
    vk_id = 600_004
    mgr_user, gear = await _seed_manager_with_vk_and_gear(test_db_session, vk_user_id=vk_id)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/integrations/vk/rental-requests",
            params={"vk_user_id": vk_id},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={
                "due_date": "03.04.2026",
                "event": "Mgr via bot",
                "comment": "m",
                "deposit_document": "m.pdf",
                "target_manager_id": mgr_user.id,
                "items": [{"gear_id": gear.id, "qty_requested": 1}],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "pending"
        assert data["event"] == "Mgr via bot"


@pytest.mark.asyncio
async def test_vk_integration_requires_secret_on_new_routes(test_db_session):
    _, gear = await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=600_002)
    target = await _seed_manager_user_plain(test_db_session, email="vk_secret_tgt@example.com")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r_no = await ac.post(
            "/api/integrations/vk/rental-requests",
            params={"vk_user_id": 600_002},
            json={
                "due_date": "02.04.2026",
                "event": "x",
                "target_manager_id": target.id,
                "items": [{"gear_id": gear.id, "qty_requested": 1}],
            },
        )
        assert r_no.status_code == 401

        r_bad = await ac.post(
            "/api/integrations/vk/rental-requests",
            params={"vk_user_id": 600_002},
            headers={"X-VK-Bot-Secret": "not-the-secret"},
            json={
                "due_date": "02.04.2026",
                "event": "x",
                "target_manager_id": target.id,
                "items": [{"gear_id": gear.id, "qty_requested": 1}],
            },
        )
        assert r_bad.status_code == 401


@pytest.mark.asyncio
async def test_vk_create_rental_request_404_unlinked(test_db_session):
    """Секрет верный, но vk_user_id не привязан к аккаунту."""
    _, gear = await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=600_003)
    target = await _seed_manager_user_plain(test_db_session, email="vk_404unl_tgt@example.com")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/integrations/vk/rental-requests",
            params={"vk_user_id": 999_999},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={
                "due_date": "02.04.2026",
                "event": "Nobody",
                "target_manager_id": target.id,
                "items": [{"gear_id": gear.id, "qty_requested": 1}],
            },
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_vk_manager_decide_403_when_member_calls_manager_route(
    test_db_session,
):
    vk_member = 600_010
    _, gear = await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=vk_member)
    target = await _seed_manager_user_plain(test_db_session, email="vk_dec403_tgt@example.com")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        c = await ac.post(
            "/api/integrations/vk/rental-requests",
            params={"vk_user_id": vk_member},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={
                "due_date": "02.04.2026",
                "event": "Trip",
                "deposit_document": "d.pdf",
                "target_manager_id": target.id,
                "items": [{"gear_id": gear.id, "qty_requested": 1}],
            },
        )
        assert c.status_code == 200
        req_id = c.json()["id"]

        forbidden = await ac.patch(
            f"/api/integrations/vk/manager/rental-requests/{req_id}",
            params={"vk_user_id": vk_member},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={"decision": "reject", "comment": "no"},
        )
        assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_vk_manager_decide_reject_success(test_db_session):
    vk_member = 600_020
    vk_mgr = 600_021
    _, gear = await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=vk_member)
    mgr = await _seed_manager_with_vk(test_db_session, vk_user_id=vk_mgr)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        c = await ac.post(
            "/api/integrations/vk/rental-requests",
            params={"vk_user_id": vk_member},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={
                "due_date": "02.04.2026",
                "event": "Trip",
                "deposit_document": "d.pdf",
                "target_manager_id": mgr.id,
                "items": [{"gear_id": gear.id, "qty_requested": 1}],
            },
        )
        assert c.status_code == 200
        req_id = c.json()["id"]

        d = await ac.patch(
            f"/api/integrations/vk/manager/rental-requests/{req_id}",
            params={"vk_user_id": vk_mgr},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={"decision": "reject", "comment": "later"},
        )
        assert d.status_code == 200
        assert d.json()["status"] == "rejected"
        assert d.json()["decision_comment"] == "later"


@pytest.mark.asyncio
async def test_vk_get_active_rentals_404_unlinked(test_db_session):
    await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=600_030)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(
            "/api/integrations/vk/rentals/active",
            params={"vk_user_id": 888_888},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_vk_create_and_approve_return_request(test_db_session):
    vk_member = 700_010
    vk_mgr = 700_011
    member, gear = await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=vk_member)
    mgr = await _seed_manager_with_vk(test_db_session, vk_user_id=vk_mgr)

    rental = await issue_rental(
        session=test_db_session,
        user_id=member.id,
        issue_manager_id=mgr.id,
        due_date=date(2026, 7, 1),
        event="VK hike",
        comment=None,
        lines=[(gear.id, 1)],
    )
    await test_db_session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        c = await ac.post(
            "/api/integrations/vk/rental-return-requests",
            params={"vk_user_id": vk_member},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={
                "rental_id": rental.id,
                "items": [{"gear_id": gear.id, "qty_return": 1}],
            },
        )
        assert c.status_code == 200
        rr_id = c.json()["id"]
        assert c.json()["status"] == "pending"

        d = await ac.patch(
            f"/api/integrations/vk/manager/rental-return-requests/{rr_id}",
            params={"vk_user_id": vk_mgr},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={"decision": "approve", "comment": "vk ok"},
        )
        assert d.status_code == 200
        assert d.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_vk_manager_can_create_return_request_own_rental(test_db_session):
    vk_mgr = 700_041
    mgr, gear = await _seed_manager_with_vk_and_gear(test_db_session, vk_user_id=vk_mgr)
    admin = User(
        email="vk_admin_issue_only@example.com",
        password_hash=hash_password("a"),
        full_name="Admin Issue Only",
        phone="+700041",
        role="admin",
    )
    test_db_session.add(admin)
    await test_db_session.commit()
    await test_db_session.refresh(admin)

    rental = await issue_rental(
        session=test_db_session,
        user_id=mgr.id,
        issue_manager_id=admin.id,
        due_date=date(2026, 8, 1),
        event="Mgr self vk",
        comment=None,
        lines=[(gear.id, 1)],
    )
    await test_db_session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        c = await ac.post(
            "/api/integrations/vk/rental-return-requests",
            params={"vk_user_id": vk_mgr},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={
                "rental_id": rental.id,
                "items": [{"gear_id": gear.id, "qty_return": 1}],
            },
        )
        assert c.status_code == 200
        assert c.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_vk_return_request_404_unlinked(test_db_session):
    await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=700_020)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/integrations/vk/rental-return-requests",
            params={"vk_user_id": 999_999_999},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={"rental_id": 1, "items": [{"gear_id": 1, "qty_return": 1}]},
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_vk_manager_return_request_403_member(test_db_session):
    vk_member = 700_030
    vk_mgr = 700_031
    member, gear = await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=vk_member)
    mgr = await _seed_manager_with_vk(test_db_session, vk_user_id=vk_mgr)

    rental = await issue_rental(
        session=test_db_session,
        user_id=member.id,
        issue_manager_id=mgr.id,
        due_date=date(2026, 7, 1),
        event="VK hike",
        comment=None,
        lines=[(gear.id, 1)],
    )
    await test_db_session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        c = await ac.post(
            "/api/integrations/vk/rental-return-requests",
            params={"vk_user_id": vk_member},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={
                "rental_id": rental.id,
                "items": [{"gear_id": gear.id, "qty_return": 1}],
            },
        )
        assert c.status_code == 200
        rr_id = c.json()["id"]

        forbidden = await ac.patch(
            f"/api/integrations/vk/manager/rental-return-requests/{rr_id}",
            params={"vk_user_id": vk_member},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={"decision": "reject", "comment": "no"},
        )
        assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_vk_list_managers_with_vk_ok_and_401(test_db_session: AsyncSession):
    vk_mgr = 800_010
    await _seed_manager_with_vk(test_db_session, vk_user_id=vk_mgr)
    test_db_session.add(
        User(
            email="only_admin@example.com",
            password_hash=hash_password("p"),
            full_name="Admin No Vk",
            phone="+8000",
            role="admin",
        )
    )
    await test_db_session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        bad = await ac.get("/api/integrations/vk/managers")
        assert bad.status_code == 401

        r = await ac.get(
            "/api/integrations/vk/managers",
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
        )
        assert r.status_code == 200
        payload = r.json()
        rows = payload["managers"]
        assert len(rows) >= 2
        by_vk = {m["vk_user_id"]: m for m in rows if m["vk_user_id"] is not None}
        assert vk_mgr in by_vk
        assert by_vk[vk_mgr]["full_name"] == "VK Manager"
        no_vk_admins = [m for m in rows if m["full_name"] == "Admin No Vk"]
        assert len(no_vk_admins) == 1
        assert no_vk_admins[0]["vk_user_id"] is None
