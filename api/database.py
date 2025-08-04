from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, BigInteger
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
db_name = os.getenv('DB_NAME')
host = os.getenv('DB_HOST')
DATABASE_URL = f"postgresql+asyncpg://{user}:{password}@{host}:5432/{db_name}"

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)

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