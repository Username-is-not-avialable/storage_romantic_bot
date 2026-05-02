from __future__ import annotations

import logging
import os
import random
import re
import sys
from typing import Any

import httpx
import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        log.error("Missing required environment variable: %s", name)
        sys.exit(1)
    return v


def _send(vk: vk_api.VkApiMethod, *, peer_id: int, text: str) -> None:
    vk.messages.send(
        peer_id=peer_id,
        message=text,
        random_id=random.randint(-2_147_483_648, 2_147_483_647),
    )


def _help_text() -> str:
    return (
        "Команды (с префиксом /):\n"
        "/старт или /help — эта справка\n"
        "/привязать <код> — связать VK с аккаунтом на сайте\n"
        "/профиль или /я — данные профиля после привязки\n\n"
        "Код: войдите на сайт в аккаунт и запросите выдачу кода "
        "(POST /api/auth/vk-link/request_code в авторизованной сессии), "
        "затем отправьте боту: /привязать <код>"
    )


def _parse_command(text: str) -> tuple[str | None, str | None]:
    t = (text or "").strip()
    if not t.startswith("/"):
        return None, None
    rest = t[1:].strip()
    if not rest:
        return None, None
    m = re.match(r"(\S+)(?:\s+(.*))?", rest, re.DOTALL)
    if not m:
        return None, None
    cmd = m.group(1).lower()
    arg = (m.group(2) or "").strip() or None
    return cmd, arg


def _api_base() -> str:
    return _env("API_BASE_URL").rstrip("/")


def _bot_secret() -> str:
    return _env("VK_BOT_SECRET")


def _link_complete(client: httpx.Client, *, code: str, vk_user_id: int) -> tuple[int, dict[str, Any]]:
    r = client.post(
        f"{_api_base()}/api/integrations/vk/link-complete",
        json={"code": code, "vk_user_id": vk_user_id},
        headers={"X-VK-Bot-Secret": _bot_secret()},
        timeout=30.0,
    )
    try:
        body: dict[str, Any] = r.json()
    except Exception:
        body = {}
    return r.status_code, body


def _me(client: httpx.Client, *, vk_user_id: int) -> tuple[int, dict[str, Any]]:
    r = client.get(
        f"{_api_base()}/api/integrations/vk/me",
        params={"vk_user_id": vk_user_id},
        headers={"X-VK-Bot-Secret": _bot_secret()},
        timeout=30.0,
    )
    try:
        body: dict[str, Any] = r.json()
    except Exception:
        body = {}
    return r.status_code, body


def main() -> None:
    token = _env("VK_GROUP_TOKEN")
    group_id = int(_env("VK_GROUP_ID"))

    vk_session = vk_api.VkApi(token=token)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id=group_id)

    log.info("VK Long Poll started for group_id=%s", group_id)

    with httpx.Client() as client:
        for event in longpoll.listen():
            if event.type != VkBotEventType.MESSAGE_NEW:
                continue
            if getattr(event, "from_chat", False) or getattr(event, "from_group", False):
                continue
            msg = event.message
            if not msg:
                continue
            text = msg.get("text") or ""
            peer_id = int(msg["peer_id"])
            from_id = int(msg.get("from_id") or peer_id)

            cmd, arg = _parse_command(text)
            if cmd is None:
                continue

            if cmd in ("старт", "start", "help"):
                _send(vk, peer_id=peer_id, text=_help_text())
                continue

            if cmd in ("привязать", "link"):
                if not arg:
                    _send(vk, peer_id=peer_id, text="Укажите код: /привязать <код>")
                    continue
                status, body = _link_complete(client, code=arg, vk_user_id=from_id)
                if status == 200:
                    name = body.get("full_name") or "пользователь"
                    _send(vk, peer_id=peer_id, text=f"Готово. Привязан профиль: {name}.")
                elif status == 400:
                    _send(vk, peer_id=peer_id, text="Код недействителен или истёк.")
                elif status == 409:
                    detail = body.get("detail", "Этот VK уже привязан к другому пользователю.")
                    _send(vk, peer_id=peer_id, text=str(detail))
                else:
                    _send(
                        vk,
                        peer_id=peer_id,
                        text=f"Ошибка сервера ({status}). Попробуйте позже.",
                    )
                continue

            if cmd in ("профиль", "я", "me", "profile"):
                status, body = _me(client, vk_user_id=from_id)
                if status == 200:
                    lines = [
                        f"Имя: {body.get('full_name', '')}",
                        f"Email: {body.get('email', '')}",
                        f"Телефон: {body.get('phone', '')}",
                        f"Роль: {body.get('role', '')}",
                    ]
                    if body.get("document"):
                        lines.append(f"Документ: {body['document']}")
                    _send(vk, peer_id=peer_id, text="\n".join(lines))
                elif status == 404:
                    _send(
                        vk,
                        peer_id=peer_id,
                        text="Аккаунт VK ещё не привязан. Используйте /привязать <код>.",
                    )
                else:
                    _send(
                        vk,
                        peer_id=peer_id,
                        text=f"Не удалось загрузить профиль ({status}).",
                    )
                continue

            _send(vk, peer_id=peer_id, text="Неизвестная команда. /help — справка.")


if __name__ == "__main__":
    main()
