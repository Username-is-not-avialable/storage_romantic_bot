from __future__ import annotations

import logging
import os
import re
from contextvars import ContextVar
from datetime import datetime, timezone

from pythonjsonlogger.core import RESERVED_ATTRS
from pythonjsonlogger.json import JsonFormatter

# Сквозной идентификатор события VK Long Poll; "-" — вне обработки события.
event_id_var: ContextVar[str] = ContextVar("event_id", default="-")

_SERVICE = "bot"

# Атрибуты LogRecord, которые не копируем в JSON (служебный шум).
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
        log_record["timestamp"] = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat(timespec="milliseconds")
        log_record["service"] = _SERVICE
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["event_id"] = event_id_var.get()
        log_record["message"] = record.message

        raw = vars(record)
        for key, value in raw.items():
            if key not in _SKIP_ATTRS and value is not None:
                log_record[key] = value

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


def configure_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(RedactingJsonFormatter(json_ensure_ascii=False))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise SystemExit(f"Missing required environment variable: {name}")
    return v


def vk_msg_max_len() -> int:
    return int(os.environ.get("VK_BOT_MESSAGE_MAX_LEN", "4000"))


def vk_link_page_url() -> str:
    return os.environ.get("VK_LINK_PAGE_URL", "").strip()
