"""Структурированное логирование API.

Каждая лог-запись — один JSON-объект. Поверх ``python-json-logger``:

- белый список полей (без шума ``LogRecord``: ``pathname``, ``thread`` и т.п.);
- сквозной ``request_id`` через ``contextvars`` (заполняется middleware);
- маскирование PII (телефон, документ, email, пароль) в глубину — работает
  даже если в лог случайно попали персональные данные.
"""
from __future__ import annotations

import logging
import os
import re
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from pythonjsonlogger.core import RESERVED_ATTRS
from pythonjsonlogger.json import JsonFormatter

# Сквозной идентификатор запроса. "-" — вне активного HTTP-запроса.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_SERVICE = "api"

# Атрибуты LogRecord, которые не копируем в JSON (служебный шум) + цветной дубль uvicorn.
_SKIP_ATTRS = frozenset(RESERVED_ATTRS) | {"color_message"}

# 1) Маскирование по ИМЕНИ КЛЮЧА — значение целиком уходит в "[redacted]".
_SENSITIVE_KEYS = frozenset((
    "password", "password_hash", "token", "authorization", "cookie",
    "session_id", "code", "secret", "vk_bot_secret",
    "phone", "document", "full_name", "email",
))

# 2) Маскирование ПО ШАБЛОНУ внутри текста: телефон RU, паспорт, email.
_PII_PATTERNS = (
    re.compile(r"\+?7[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"),
    re.compile(r"\b[А-Яа-яЁё]+\s+\d{4}\s+\d{6}\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)

_REDACTED = "[redacted]"


def _redact_text(value: str) -> str:
    for pattern in _PII_PATTERNS:
        value = pattern.sub(_REDACTED, value)
    return value


def _redact_value(value):
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_redact_value(item) for item in value]
    return value


class RedactingJsonFormatter(JsonFormatter):
    """JsonFormatter с белым списком полей и маскированием PII."""

    def add_fields(self, log_record, record, message_dict) -> None:
        # Ядро: ничего лишнего из LogRecord не берём.
        log_record["timestamp"] = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat(timespec="milliseconds")
        log_record["service"] = _SERVICE
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["request_id"] = request_id_var.get()
        # record.message уже выставлен базой: getMessage() либо "" для dict-msg.
        log_record["message"] = record.message

        raw = vars(record)
        for key, value in raw.items():
            # Копируем только явные extra (extra kwargs), не служебные атрибуты.
            # PII среди них отмаскируется в process_log_record.
            if key not in _SKIP_ATTRS and value is not None:
                log_record[key] = value

        # Структурный лог (logger.info({...})): мержим поля словаря.
        for key, value in message_dict.items():
            if key != "message":
                log_record[key] = value

    def process_log_record(self, log_record):
        cleaned = {}
        for key, value in log_record.items():
            if key.lower() in _SENSITIVE_KEYS:
                cleaned[key] = _REDACTED
            else:
                cleaned[key] = _redact_value(value)
        log_record.clear()
        log_record.update(cleaned)
        return log_record


def setup_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(RedactingJsonFormatter(json_ensure_ascii=False))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn настраивает свои логгеры в Config.__init__ — ДО импорта приложения,
    # поэтому наш setup_logging() на импорте перекрывает их корректно.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        # access-лог uvicorn отключаем: пишем свой через логгер "access".
        logger.setLevel(logging.WARNING if name == "uvicorn.access" else level)
        logger.propagate = False

    access = logging.getLogger("access")
    access.handlers = [handler]
    access.setLevel(level)
    access.propagate = False


class RequestIdMiddleware:
    """ASGI middleware: сквозной request_id + JSON access-лог.

    Чистая ASGI-middleware (не BaseHTTPMiddleware), чтобы контекст
    ``contextvars`` гарантированно был виден эндпоинту и его логам.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code: int | None = None

        async def _send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = [
                    h for h in message.get("headers", [])
                    if h[0].lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, _send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            access = logging.getLogger("access")
            if status_code is None:
                access.error("request failed", extra={
                    "method": scope.get("method", ""),
                    "path": scope.get("path", ""),
                })
            else:
                access.info("request completed", extra={
                    "method": scope.get("method", ""),
                    "path": scope.get("path", ""),
                    "status": status_code,
                    "duration_ms": duration_ms,
                })
            request_id_var.reset(token)