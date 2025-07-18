from fastapi import FastAPI
from api.routers import users, gear, rentals
from api.database import engine, Base

app = FastAPI(title="storage Romantic API")

# Подключение роутеров
app.include_router(users.router)
app.include_router(gear.router)
app.include_router(rentals.router)

@app.on_event("startup")
async def init_db():
    # Создание таблиц (если не Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)