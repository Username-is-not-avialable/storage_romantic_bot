from fastapi import FastAPI
from api.config import get_settings
from api.routers import rental_requests, users, gear, rentals

get_settings()  # validate required env at startup/import time

app = FastAPI(title="storage Romantic API")

# Подключение роутеров
app.include_router(users.router)
app.include_router(gear.router)
app.include_router(rentals.router)
app.include_router(rental_requests.router)
app.include_router(rental_requests.manager_router)