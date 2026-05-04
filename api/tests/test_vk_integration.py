from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import Gear, User, UserMessengerLink
from api.main import app
from api.services.auth import hash_password

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


@pytest.mark.asyncio
async def test_vk_create_rental_request_success(test_db_session):
    vk_id = 600_001
    _, gear = await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=vk_id)
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
async def test_vk_integration_requires_secret_on_new_routes(test_db_session):
    await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=600_002)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r_no = await ac.post(
            "/api/integrations/vk/rental-requests",
            params={"vk_user_id": 600_002},
            json={
                "due_date": "02.04.2026",
                "event": "x",
                "items": [{"gear_id": 1, "qty_requested": 1}],
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
                "items": [{"gear_id": 1, "qty_requested": 1}],
            },
        )
        assert r_bad.status_code == 401


@pytest.mark.asyncio
async def test_vk_create_rental_request_404_unlinked(test_db_session):
    """Секрет верный, но vk_user_id не привязан к аккаунту."""
    await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=600_003)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/integrations/vk/rental-requests",
            params={"vk_user_id": 999_999},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={
                "due_date": "02.04.2026",
                "event": "Nobody",
                "items": [{"gear_id": 1, "qty_requested": 1}],
            },
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_vk_manager_decide_403_when_member_calls_manager_route(
    test_db_session,
):
    vk_member = 600_010
    _, gear = await _seed_member_with_vk_and_gear(test_db_session, vk_user_id=vk_member)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        c = await ac.post(
            "/api/integrations/vk/rental-requests",
            params={"vk_user_id": vk_member},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={
                "due_date": "02.04.2026",
                "event": "Trip",
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
    await _seed_manager_with_vk(test_db_session, vk_user_id=vk_mgr)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        c = await ac.post(
            "/api/integrations/vk/rental-requests",
            params={"vk_user_id": vk_member},
            headers={"X-VK-Bot-Secret": TEST_VK_SECRET},
            json={
                "due_date": "02.04.2026",
                "event": "Trip",
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
