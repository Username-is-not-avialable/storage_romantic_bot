from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import User
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
