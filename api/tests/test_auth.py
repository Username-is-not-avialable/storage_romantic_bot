import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import User
from api.main import app
from api.services.auth import hash_password


async def _seed_user(session: AsyncSession) -> None:
    session.add(
        User(
            email="member@example.com",
            password_hash=hash_password("memberpass"),
            full_name="Member",
            phone="+100",
            role="member",
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_login_me_logout_flow(test_db_session: AsyncSession):
    await _seed_user(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        me_before = await ac.get("/api/auth/me")
        assert me_before.status_code == 401

        login = await ac.post(
            "/api/auth/login",
            json={"email": "member@example.com", "password": "memberpass"},
        )
        assert login.status_code == 200

        me_after = await ac.get("/api/auth/me")
        assert me_after.status_code == 200
        assert me_after.json()["email"] == "member@example.com"

        logout = await ac.post("/api/auth/logout")
        assert logout.status_code == 200

        me_after_logout = await ac.get("/api/auth/me")
        assert me_after_logout.status_code == 401
