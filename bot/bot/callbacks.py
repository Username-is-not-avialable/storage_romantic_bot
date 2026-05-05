from __future__ import annotations

import json
from typing import Any

import vk_api

from bot.api_client import IntegrationClient, format_api_error
from bot.flows.notifications import rental_decision_member_text, return_decision_member_text
from bot.notify_registry import rental_applicant_peer, return_applicant_peer
from bot.vk_send import ack_message_event, send_peer, try_edit_remove_keyboard


def _parse_payload(payload_raw: Any) -> dict[str, Any]:
    if payload_raw is None:
        return {}
    if isinstance(payload_raw, dict):
        return payload_raw
    if isinstance(payload_raw, str):
        s = payload_raw.strip()
        if not s:
            return {}
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def handle_message_event(
    vk: vk_api.VkApiMethod,
    api: IntegrationClient,
    event: Any,
) -> None:
    obj = event.obj
    manager_vk_user_id = int(obj.user_id)
    peer_id = int(obj.peer_id)
    event_id = obj.get("event_id")
    cmid = obj.get("conversation_message_id")
    payload = _parse_payload(obj.get("payload"))

    kind = str(payload.get("t") or "")
    try:
        req_id = int(payload["i"])
    except (KeyError, TypeError, ValueError):
        ack_message_event(
            vk,
            event_id=event_id,
            user_id=manager_vk_user_id,
            peer_id=peer_id,
            text="Некорректная кнопка.",
        )
        return

    approve = str(payload.get("d")) == "a"
    decision = "approve" if approve else "reject"

    if kind == "rq":
        sc, body = api.decide_rental_request(
            manager_vk_user_id=manager_vk_user_id,
            rental_request_id=req_id,
            decision=decision,
            comment=None,
        )
    elif kind == "rt":
        sc, body = api.decide_return_request(
            manager_vk_user_id=manager_vk_user_id,
            return_request_id=req_id,
            decision=decision,
            comment=None,
        )
    else:
        ack_message_event(
            vk,
            event_id=event_id,
            user_id=manager_vk_user_id,
            peer_id=peer_id,
            text="Неизвестное действие.",
        )
        return

    if sc == 200:
        snack = "Принято." if approve else "Отклонено."
        ack_message_event(
            vk,
            event_id=event_id,
            user_id=manager_vk_user_id,
            peer_id=peer_id,
            text=snack,
        )
        try_edit_remove_keyboard(vk, peer_id=peer_id, conversation_message_id=cmid)

        detail_comment = body.get("decision_comment") if isinstance(body.get("decision_comment"), str) else None
        if kind == "rq":
            member_peer = rental_applicant_peer.pop(req_id, None)
            if member_peer is not None:
                mt = rental_decision_member_text(
                    approved=approve,
                    detail=detail_comment,
                    req_id=req_id,
                )
                send_peer(vk, peer_id=int(member_peer), text=mt)
        elif kind == "rt":
            member_peer = return_applicant_peer.pop(req_id, None)
            if member_peer is not None:
                mt = return_decision_member_text(
                    approved=approve,
                    detail=detail_comment,
                    req_id=req_id,
                )
                send_peer(vk, peer_id=int(member_peer), text=mt)
        return

    err_txt = format_api_error(body if isinstance(body, dict) else {})
    low = err_txt.lower()
    if sc == 400 and ("уже решена" in low or "already" in low):
        snack = "Уже обработано."
    elif sc == 403:
        snack = "Недостаточно прав."
    elif sc == 404:
        snack = "Заявка не найдена."
    else:
        snack = err_txt[:220]

    ack_message_event(
        vk,
        event_id=event_id,
        user_id=manager_vk_user_id,
        peer_id=peer_id,
        text=snack,
    )
