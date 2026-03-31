from fastapi import FastAPI
from api.routers import users, gear, rentals

app = FastAPI(title="storage Romantic API")

# Подключение роутеров
app.include_router(users.router)
app.include_router(gear.router)
app.include_router(rentals.router)