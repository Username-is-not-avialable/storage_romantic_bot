from fastapi import FastAPI
from api.config import get_settings
from api.routers import admin, auth, rental_requests, users, gear, rentals, vk_integration

get_settings()  # validate required env at startup/import time

app = FastAPI(title="storage Romantic API")

# Подключение роутеров
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(gear.router)
app.include_router(rentals.router)
app.include_router(rental_requests.router)
app.include_router(rental_requests.manager_router)
app.include_router(admin.router)
app.include_router(vk_integration.auth_vk_router)
app.include_router(vk_integration.integrations_router)