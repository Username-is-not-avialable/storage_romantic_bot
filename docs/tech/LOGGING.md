# LOGGING: логирование и observability

Документ фиксирует, как сервисы пишут логи, как они собираются и где их смотреть (веб-интерфейс вместо `docker logs`).

## 1. Общая схема

```
api / bot / web / db ──stdout──▶ Docker (json-file) ──▶ promtail ──▶ loki ──▶ grafana (UI)
```

| Компонент | Роль | Конфиг |
|---|---|---|
| Приложения | пишут JSON-логи в stdout | `api/logging_config.py`, `bot/bot/config.py` |
| Docker | ротация лог-файлов контейнера | `docker-compose.yml` (`logging:`) |
| promtail | читает логи контейнеров через `docker.sock`, вешает метки, шлёт в Loki | `infra/promtail/promtail.yml` |
| loki | хранит и индексирует логи (retention 7 дней) | `infra/loki/loki.yml` |
| grafana | веб-интерфейс поиска/фильтрации логов | `infra/grafana/provisioning/` |

`docker logs` продолжает работать: promtail читает те же `json-file` логи параллельно, лог-драйвер контейнеров не меняется.

## 2. Формат логов приложений (api, bot)

Каждая запись — один JSON-объект (форматтер на базе `python-json-logger`). Базовые поля:

| Поле | Значение |
|---|---|
| `timestamp` | ISO-8601, UTC |
| `service` | `api` или `bot` |
| `level` | `INFO` / `WARNING` / `ERROR` |
| `logger` | имя логгера (например `api.routers.auth`) |
| `message` | текст сообщения |
| `request_id` (api) / `event_id` (bot) | сквозной идентификатор; `-` вне запроса/события |

Дополнительные поля:

- **access-лог api** (пишет middleware; стандартный `uvicorn.access` отключён): `method`, `path`, `status`, `duration_ms`.
- **bot**: `event_type`, `user_id` — в момент обработки события VK; текст сообщений пользователей не логируется.

Пример access-лога:

```json
{"timestamp": "2026-09-11T12:00:00.000+00:00", "service": "api", "level": "INFO", "logger": "access", "request_id": "7f1c…", "message": "request completed", "method": "POST", "path": "/api/auth/login", "status": 200, "duration_ms": 42.0}
```

Механизм `request_id`: middleware генерирует UUID на каждый HTTP-запрос, кладёт его в `contextvars` (значение видно всем логам внутри запроса; у конкурентных запросов не путается) и возвращает в заголовке ответа `X-Request-ID`. В логе он проставляется через logging-фильтр из `ContextVar`.

Настройка логгеров api выполняется на импорте `api.main` (`setup_logging()`): uvicorn настраивает свои логгеры до загрузки приложения, поэтому такой вызов корректно перекрывает их (включая `uvicorn`, `uvicorn.error`).

Уровень логов управляется переменной `LOG_LEVEL` (по умолчанию `INFO`).

## 3. Маскирование PII

Правило: персональные данные (phone/document/email/пароли) не попадают в логи в открытом виде. Защита двухуровневая:

1. **По имени поля** — значение ключей `phone`, `document`, `email`, `password`, `password_hash`, `token`, `secret`, `authorization`, `cookie`, `session_id`, `code`, `full_name` заменяется на `[redacted]` целиком.
2. **По шаблону в тексте** — телефон (+7…), серия/номер паспорта, email вырезаются из строки сообщения.

Реализовано в `RedactingJsonFormatter` (`api/logging_config.py` и `bot/bot/config.py`), покрыто тестами (`api/tests/test_logging_config.py`). Списки расширяются в `_SENSITIVE_KEYS` и `_PII_PATTERNS`.

## 4. Сбор, хранение и ротация

- promtail автоматически находит контейнеры (`docker_sd`), метки: `service` (имя compose-сервиса), `container`, `stream` (stdout/stderr). Из JSON-логов `level` поднимается в метку; `request_id`/`status` остаются в тексте записи и фильтруются через LogQL (намеренно без high-cardinality меток).
- loki хранит логи **7 дней** (`limits_config.retention_period`), затем удаляет.
- Docker-ротация: `json-file`, `max-size: 10m`, `max-file: 3` — не более ~30 МБ логов на контейнер.

## 5. Просмотр в Grafana

- UI: `http://localhost:3000`; анонимный доступ в роли Viewer, полный доступ — admin (`GRAFANA_ADMIN_PASSWORD` из `.env`).
- Датасорс Loki провиженится автоматически (`infra/grafana/provisioning/datasources/loki.yml`).

Примеры LogQL (Explore → Loki):

| Что ищем | Запрос |
|---|---|
| Все логи API | `{service="api"}` |
| Ошибки | `{service="api", level="ERROR"}` |
| Логи одного запроса | `{service=~"api\|bot"} \| json \| request_id="7f1c…"` |
| Медленные запросы (>1 c) | `{service="api"} \| json \| duration_ms > 1000` |
| Ответы 5xx | `{service="api"} \| json \| status >= 500` |

## 6. Расширение

- Новое поле в лог: `log.info("msg", extra={"entity": "rental", "action": "issue"})` — любое неслужебное `extra` попадает в JSON и проходит маскирование.
- События бота: выставить `event_id_var.set(...)` в обработчике Long Poll — все логи одного события получат общий `event_id` (сейчас контекст объявлен, но не проставляется).
- Новые лоукардинальные поля (например `event_type`) можно поднять в метки Loki в `infra/promtail/promtail.yml`.
