## Romantic Storage Bot

Кросс-платформенный сервис и бот для управления арендой и хранением снаряжения: учет вещей, статусов, арендаторов и операций, с API, веб-интерфейсом и интеграцией с мессенджерами.

### Быстрый старт

```bash
docker compose up -d
```

API будет доступно на `http://localhost:8100`.

### Миграции БД (Alembic)

```bash
docker compose run --rm api alembic -c api/alembic.ini upgrade head
```