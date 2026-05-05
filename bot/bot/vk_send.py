from __future__ import annotations

import json
import logging
import random
from typing import Any

import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from bot.config import vk_msg_max_len

log = logging.getLogger(__name__)


def chunked_text(text: str) -> list[str]:
    n = vk_msg_max_len()
    if len(text) <= n:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        chunk = text[start : start + n]
        parts.append(chunk)
        start += n
    return parts


def send_peer(
    vk: vk_api.VkApiMethod,
    *,
    peer_id: int,
    text: str,
    keyboard: str | None = None,
) -> int | None:
    """Отправка текста (с разбиением). Возвращает conversation_message_id последней части, если API вернул."""
    last_cm: int | None = None
    for part in chunked_text(text):
        params: dict[str, Any] = {
            "peer_id": peer_id,
            "message": part,
            "random_id": random.randint(-2_147_483_648, 2_147_483_647),
        }
        if keyboard is not None:
            params["keyboard"] = keyboard
        raw = vk.messages.send(**params)
        if isinstance(raw, dict):
            last_cm = raw.get("conversation_message_id") or raw.get("message_id")
        elif isinstance(raw, int):
            last_cm = raw
    return last_cm if isinstance(last_cm, int) else None


def inline_keyboard_two_actions(
    *,
    accept_payload: str | dict[str, Any],
    reject_payload: str | dict[str, Any],
    accept_label: str = "Принять",
    reject_label: str = "Отклонить",
) -> str:
    """Inline-клавиатура: два callback (payload — строка или dict, сериализуется в JSON)."""
    kb = VkKeyboard(inline=True)
    kb.add_callback_button(
        accept_label,
        color=VkKeyboardColor.POSITIVE,
        payload=accept_payload,
    )
    kb.add_callback_button(
        reject_label,
        color=VkKeyboardColor.NEGATIVE,
        payload=reject_payload,
    )
    return kb.get_keyboard()


def empty_keyboard() -> str:
    return VkKeyboard.get_empty_keyboard()


def ack_message_event(
    vk: vk_api.VkApiMethod,
    *,
    event_id: str | int | None,
    user_id: int,
    peer_id: int,
    text: str = " ",
) -> None:
    """Снять «крутилку» у callback-кнопки (snackbar опционально через event_data)."""
    if event_id is None:
        return
    try:
        vk.messages.sendMessageEventAnswer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            event_data=json.dumps(
                {"type": "show_snackbar", "text": text[:255]},
                ensure_ascii=False,
            ),
        )
    except Exception as exc:
        log.warning("sendMessageEventAnswer failed: %s", exc)


def try_edit_remove_keyboard(
    vk: vk_api.VkApiMethod,
    *,
    peer_id: int,
    conversation_message_id: int | None,
    new_text: str | None = None,
) -> bool:
    if conversation_message_id is None:
        return False
    try:
        vk.messages.edit(
            peer_id=peer_id,
            conversation_message_id=conversation_message_id,
            message=new_text or " ",
            keyboard=empty_keyboard(),
        )
        return True
    except Exception as exc:
        log.warning("messages.edit failed: %s", exc)
        return False
