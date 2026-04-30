import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import User
from api.main import app


async def _seed_users(session: AsyncSession) -> None:
    session.add_all(
        [
            User(id_telegram=1, full_name="Member", phone="+100", role="member"),
            User(id_telegram=2, full_name="Manager", phone="+200", role="manager"),
            User(id_telegram=3, full_name="Admin", phone="+300", role="admin"),
        ]
    )
    await session.commit()


@pytest.mark.asyncio
async def test_member_cannot_create_gear(test_db_session: AsyncSession):
    await _seed_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/gear/?user_id=1",
            json={
                "name": "Tent",
                "total_quantity": 5,
                "available_count": 5,
                "description": "t",
            },
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_manager_can_create_gear(test_db_session: AsyncSession):
    await _seed_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/gear/?user_id=2",
            json={
                "name": "Tent2",
                "total_quantity": 5,
                "available_count": 5,
                "description": "t",
            },
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_member_cannot_list_admin_users(test_db_session: AsyncSession):
    await _seed_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/admin/users?user_id=1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_list_admin_users(test_db_session: AsyncSession):
    await _seed_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/admin/users?user_id=2")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_admin_users(test_db_session: AsyncSession):
    await _seed_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/admin/users?user_id=3")
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
