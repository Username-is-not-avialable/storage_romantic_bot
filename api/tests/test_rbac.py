import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, User, get_db
from api.main import app


@pytest_asyncio.fixture
async def test_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture(autouse=True)
def override_get_db(test_db_session: AsyncSession):
    async def _override():
        yield test_db_session

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.pop(get_db, None)


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
            "/api/gear/?id_telegram=1",
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
            "/api/gear/?id_telegram=2",
            json={
                "name": "Tent2",
                "total_quantity": 5,
                "available_count": 5,
                "description": "t",
            },
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_member_cannot_search_users(test_db_session: AsyncSession):
    await _seed_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/users/search/?id_telegram=1", json={})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_manager_can_search_users(test_db_session: AsyncSession):
    await _seed_users(test_db_session)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/users/search/?id_telegram=2", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
