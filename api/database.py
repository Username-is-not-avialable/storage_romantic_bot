import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import BigInteger, Boolean, Column, Date, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()


def _build_database_urls() -> tuple[str, str]:
    """
    Возвращает пару (sync_url, async_url).

    - sync_url используется Alembic (psycopg2)
    - async_url используется приложением (asyncpg)
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        sync_url = env_url
    else:
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        db_name = os.getenv("DB_NAME")
        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT") or "5432"
        sync_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

    async_url = (
        sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if sync_url.startswith("postgresql://")
        else sync_url
    )
    return sync_url, async_url


SYNC_DATABASE_URL, ASYNC_DATABASE_URL = _build_database_urls()

engine = create_async_engine(ASYNC_DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Базовый класс для моделей
Base = declarative_base()

# Модель пользователя
class User(Base):
    __tablename__ = "users"

    id_telegram = Column(BigInteger, primary_key=True)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    document = Column(String(100), nullable=True)
    is_manager = Column(Boolean, default=False)

# Модель снаряжения
class Gear(Base):
    __tablename__ = "gear"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    total_quantity = Column(Integer, nullable=False)
    available_count = Column(Integer, nullable=False)
    description = Column(String(500), nullable=True)

# Модель аренды
class Rental(Base):
    __tablename__ = "rentals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_telegram_id = Column(BigInteger, ForeignKey("users.id_telegram"), nullable=False)
    issue_manager_tg_id = Column(BigInteger, ForeignKey("users.id_telegram"), nullable=False)
    accept_manager_tg_id = Column(BigInteger, ForeignKey("users.id_telegram"), nullable=True)
    gear_id = Column(Integer, ForeignKey("gear.id"), nullable=False)
    issue_date = Column(Date, default=datetime.utcnow, nullable=False)
    due_date = Column(Date, nullable=False)
    return_date = Column(Date, nullable=True)
    quantity = Column(Integer, nullable=False)
    event = Column(String(300), nullable=False) #TODO: определить подходящее ограничение
    comment = Column(String(300), nullable=True) #TODO: определить подходящее ограничение

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session