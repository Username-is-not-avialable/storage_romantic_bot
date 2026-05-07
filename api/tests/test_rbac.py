import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import User
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


@pytest.mark.asyncio
async def test_member_cannot_create_gear(test_db_session: AsyncSession):
    await _seed_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        login = await ac.post("/api/auth/login", json={"email": "member@example.com", "password": "memberpass"})
        assert login.status_code == 200
        resp = await ac.post(
            "/api/gear/",
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
        login = await ac.post("/api/auth/login", json={"email": "manager@example.com", "password": "managerpass"})
        assert login.status_code == 200
        resp = await ac.post(
            "/api/gear/",
            json={
                "name": "Tent2",
                "total_quantity": 5,
                "available_count": 5,
                "description": "t",
            },
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_member_can_list_managers_for_web(test_db_session: AsyncSession):
    await _seed_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        anon = await ac.get("/api/users/managers")
        assert anon.status_code == 401

        login = await ac.post("/api/auth/login", json={"email": "member@example.com", "password": "memberpass"})
        assert login.status_code == 200
        resp = await ac.get("/api/users/managers")
    assert resp.status_code == 200
    data = resp.json()
    assert "managers" in data
    assert len(data["managers"]) == 2
    names = {m["full_name"] for m in data["managers"]}
    assert names == {"Manager", "Admin"}


@pytest.mark.asyncio
async def test_member_cannot_list_admin_users(test_db_session: AsyncSession):
    await _seed_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        login = await ac.post("/api/auth/login", json={"email": "member@example.com", "password": "memberpass"})
        assert login.status_code == 200
        resp = await ac.get("/api/admin/users")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_list_admin_users(test_db_session: AsyncSession):
    await _seed_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        login = await ac.post("/api/auth/login", json={"email": "manager@example.com", "password": "managerpass"})
        assert login.status_code == 200
        resp = await ac.get("/api/admin/users")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_admin_users(test_db_session: AsyncSession):
    await _seed_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        login = await ac.post("/api/auth/login", json={"email": "admin@example.com", "password": "adminpass"})
        assert login.status_code == 200
        resp = await ac.get("/api/admin/users")
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
