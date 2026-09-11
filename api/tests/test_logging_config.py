import json
import logging

import pytest

from api.logging_config import (
    RedactingJsonFormatter,
    RequestIdMiddleware,
    request_id_var,
)


def _format(extra: dict | None = None, msg: str = "hello") -> dict:
    fmtr = RedactingJsonFormatter()
    record = logging.LogRecord(
        "api.test", logging.INFO, __file__, 1, msg, (), None
    )
    for key, value in (extra or {}).items():
        setattr(record, key, value)
    return json.loads(fmtr.format(record))


def test_core_fields_present():
    data = _format()
    assert set(data) == {
        "timestamp", "service", "level", "logger", "request_id", "message",
    }
    assert data["service"] == "api"
    assert data["level"] == "INFO"
    assert data["logger"] == "api.test"
    assert data["message"] == "hello"
    assert data["request_id"] == "-"


def test_request_id_from_contextvar():
    token = request_id_var.set("req-123")
    try:
        assert _format()["request_id"] == "req-123"
    finally:
        request_id_var.reset(token)


def test_extra_fields_are_included():
    data = _format(extra={
        "method": "POST", "path": "/api/auth/login",
        "status": 200, "duration_ms": 42,
    })
    assert data["method"] == "POST"
    assert data["path"] == "/api/auth/login"
    assert data["status"] == 200
    assert data["duration_ms"] == 42


def test_sensitive_key_masked():
    data = _format(extra={"phone": "+79001001001", "password": "secret"})
    assert data["phone"] == "[redacted]"
    assert data["password"] == "[redacted]"


def test_pii_patterns_in_message_masked():
    data = _format(
        msg="user +79001001001, Паспорт 0000 000000, a@b.ru",
    )
    assert "+79001001001" not in data["message"]
    assert "0000 000000" not in data["message"]
    assert "a@b.ru" not in data["message"]
    assert "[redacted]" in data["message"]


def test_no_noise_fields_from_logrecord():
    data = _format()
    for noise in ("pathname", "lineno", "thread", "process", "msecs", "args"):
        assert noise not in data


def test_middleware_sets_request_id_header_and_access_log():
    import asyncio
    import io

    captured: dict = {}

    async def app(scope, receive, send):
        captured["request_id"] = request_id_var.get()
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({"type": "http.response.body", "body": b"ok"})

    async def run():
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "headers": [],
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            captured.setdefault("responses", []).append(message)

        middleware = RequestIdMiddleware(app)
        await middleware(scope, receive, send)

    # Ловим JSON access-лог напрямую (у "access" propagate=False, caplog не увидит).
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingJsonFormatter())
    access_logger = logging.getLogger("access")
    old_handlers = access_logger.handlers[:]
    access_logger.handlers = [handler]
    try:
        asyncio.run(run())
    finally:
        access_logger.handlers = old_handlers

    # request_id доступен внутри запроса и в заголовке ответа
    request_id = captured["request_id"]
    assert request_id != "-"

    response_headers = {
        k.decode(): v.decode()
        for k, v in captured["responses"][0]["headers"]
    }
    assert response_headers["x-request-id"] == request_id

    data = json.loads(stream.getvalue().strip())
    assert data["service"] == "api"
    assert data["logger"] == "access"
    assert data["request_id"] == request_id
    assert data["method"] == "GET"
    assert data["path"] == "/api/test"
    assert data["status"] == 200
    assert "duration_ms" in data


def test_middleware_resets_context_after_request():
    import asyncio

    async def app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        })
        await send({"type": "http.response.body", "body": b""})

    async def run():
        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            pass

        await RequestIdMiddleware(app)(scope, receive, send)
        # после запроса контекст сброшен
        assert request_id_var.get() == "-"

    asyncio.run(run())


def test_setup_logging_uvicorn_handlers_are_json():
    from api.logging_config import setup_logging

    setup_logging()
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        assert logger.handlers, f"{name} has no handler"
        assert isinstance(logger.handlers[0].formatter, RedactingJsonFormatter)
        assert logger.propagate is False
    assert logging.getLogger("uvicorn.access").level == logging.WARNING

    # restore to not leak into other tests
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers = []