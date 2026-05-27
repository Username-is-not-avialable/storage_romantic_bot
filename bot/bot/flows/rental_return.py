from __future__ import annotations

import logging
from typing import Any

import vk_api

from bot.api_client import IntegrationClient, format_api_error
from bot.notify_registry import return_applicant_peer
from bot.state import DialogState, get_state
from bot.vk_send import (
    empty_keyboard,
    inline_keyboard_issue_qty,
    inline_keyboard_two_actions,
    keyboard_return_actions,
    send_peer,
)

from .notifications import callback_payload_return_decide, format_return_notification

log = logging.getLogger(__name__)

RETURN_PICK_RENTAL = "return_rental"
RETURN_PICK_ITEMS = "return_items"
RETURN_PICK_MANAGER = "return_manager"

_DONE = frozenset({"готово", "done", "далее"})


def return_gear_payload(*, gear_id: int, delta: int) -> dict[str, Any]:
    return {"t": "rg", "g": int(gear_id), "d": int(delta)}


def _merge_return_cart(cart: list[tuple[int, int]]) -> list[dict[str, int]]:
    m: dict[int, int] = {}
    for gid, q in cart:
        m[gid] = m.get(gid, 0) + q
    return [{"gear_id": g, "qty_return": q} for g, q in sorted(m.items())]


def _return_cart_summary(st: DialogState) -> str:
    merged = _merge_return_cart(st.return_cart)
    lines = []
    for it in merged:
        gid = it["gear_id"]
        label = next(
            (str(li.get("gear_name")) for li in st.return_lines if int(li["gear_id"]) == gid),
            f"id {gid}",
        )
        lines.append(f"• {label} ×{it['qty_return']}")
    return "\n".join(lines) if lines else "(пусто)"


def start_return_flow(vk: vk_api.VkApiMethod, api: IntegrationClient, peer_id: int, from_id: int) -> None:
    st = get_state(peer_id)
    code, me_body = api.me(vk_user_id=from_id)
    if code == 404:
        send_peer(vk, peer_id=peer_id, text="Сначала привяжите аккаунт: /link.")
        return
    if code != 200:
        send_peer(vk, peer_id=peer_id, text=f"Не удалось проверить профиль ({code}). {format_api_error(me_body)}")
        return
    if me_body.get("role") not in {"member", "manager", "admin"}:
        send_peer(
            vk,
            peer_id=peer_id,
            text="Заявку на возврат через бот могут оформить участники, менеджеры и администраторы.",
        )
        return

    mc, mbody = api.managers()
    if mc != 200:
        send_peer(vk, peer_id=peer_id, text=f"Не удалось загрузить завснаров ({mc}). {format_api_error(mbody)}")
        return
    vk_managers = [m for m in (mbody.get("managers") or []) if m.get("vk_user_id")]
    if not vk_managers:
        send_peer(
            vk,
            peer_id=peer_id,
            text="Нет завснаров с привязкой VK — сценарий возврата из бота недоступен.",
        )
        return

    rc, rbody = api.active_rentals(vk_user_id=from_id)
    if rc != 200:
        send_peer(vk, peer_id=peer_id, text=f"Не удалось загрузить аренды ({rc}). {format_api_error(rbody)}")
        return
    rentals = list(rbody.get("rentals") or [])
    if not rentals:
        send_peer(vk, peer_id=peer_id, text="У вас нет активных аренд для возврата.")
        return

    st.flow = "return"
    st.step = RETURN_PICK_RENTAL
    st.return_rentals = rentals
    st.return_rental_id = None
    st.return_lines.clear()
    st.return_cart.clear()
    st.return_managers = vk_managers

    lines = ["Ваши активные аренды. Выберите номер строки для возврата:"]
    for i, r in enumerate(rentals, start=1):
        rid = r.get("id")
        ev = r.get("event", "")
        lines.append(f"{i}. №{rid} — {ev}")
    send_peer(vk, peer_id=peer_id, text="\n".join(lines), keyboard=empty_keyboard())


def handle_return_text(
    vk: vk_api.VkApiMethod,
    api: IntegrationClient,
    peer_id: int,
    from_id: int,
    text: str,
) -> None:
    st = get_state(peer_id)
    assert st.flow == "return"
    raw = (text or "").strip()
    low = raw.lower()

    if st.step == RETURN_PICK_RENTAL:
        try:
            n = int(raw)
        except ValueError:
            send_peer(vk, peer_id=peer_id, text="Ответьте номером аренды из списка.")
            return
        if n < 1 or n > len(st.return_rentals):
            send_peer(vk, peer_id=peer_id, text="Номер вне списка.")
            return
        rental = st.return_rentals[n - 1]
        st.return_rental_id = int(rental["id"])
        items = list(rental.get("items") or [])
        st.return_lines = items
        st.return_cart.clear()
        if not items:
            send_peer(vk, peer_id=peer_id, text="В этой аренде нет позиций для возврата.")
            return
        lines = [f"Аренда №{st.return_rental_id}: выберите позиции для сдачи кнопками +/-."]
        send_peer(vk, peer_id=peer_id, text="\n".join(lines), keyboard=keyboard_return_actions())
        st.return_item_message_ids.clear()
        for i, it in enumerate(items, start=1):
            gid = it.get("gear_id")
            nm = it.get("gear_name", "")
            out = it.get("qty_outstanding", 0)
            text = f"{i}. {nm} — к возврату до {out} шт."
            cmid = send_peer(
                vk,
                peer_id=peer_id,
                text=text,
                keyboard=inline_keyboard_issue_qty(
                    minus_payload=return_gear_payload(gear_id=int(gid), delta=-1),
                    plus_payload=return_gear_payload(gear_id=int(gid), delta=1),
                ),
            )
            if cmid is not None:
                st.return_item_message_ids[int(gid)] = cmid
        st.step = RETURN_PICK_ITEMS
        return

    if st.step == RETURN_PICK_ITEMS:
        if low in {"выбрать все", "all"}:
            st.return_cart = []
            for it in st.return_lines:
                gid = int(it["gear_id"])
                out = int(it.get("qty_outstanding") or 0)
                if out > 0:
                    st.return_cart.append((gid, out))
            send_peer(vk, peer_id=peer_id, text="Выбраны все доступные позиции.", keyboard=keyboard_return_actions())
            return
        if low in {"посмотреть выбранные позиции", "выбранные позиции"}:
            send_peer(
                vk,
                peer_id=peer_id,
                text="Выбранные позиции для сдачи:\n" + _return_cart_summary(st),
                keyboard=keyboard_return_actions(),
            )
            return
        if low in _DONE:
            if not st.return_cart:
                send_peer(vk, peer_id=peer_id, text="Выберите хотя бы одну позицию.")
                return
            st.step = RETURN_PICK_MANAGER
            mlines = ["Кому сдавать (target_manager_id). Выберите номер завснара:"]
            for i, m in enumerate(st.return_managers, start=1):
                mlines.append(f"{i}. {m.get('full_name')} ({m.get('role')})")
            send_peer(vk, peer_id=peer_id, text="\n".join(mlines), keyboard=empty_keyboard())
            return
        send_peer(vk, peer_id=peer_id, text="Используйте кнопки +/- у позиций или «Выбрать все»/«Готово».", keyboard=keyboard_return_actions())
        return

    if st.step == RETURN_PICK_MANAGER:
        try:
            n = int(raw)
        except ValueError:
            send_peer(vk, peer_id=peer_id, text="Ответьте номером завснара.")
            return
        if n < 1 or n > len(st.return_managers):
            send_peer(vk, peer_id=peer_id, text="Номер вне списка.")
            return
        mgr = st.return_managers[n - 1]
        target_manager_id = int(mgr["user_id"])

        body: dict[str, Any] = {
            "rental_id": int(st.return_rental_id),
            "target_manager_id": target_manager_id,
            "items": _merge_return_cart(st.return_cart),
        }
        sc, sbody = api.post_return_request(vk_user_id=from_id, body=body)
        if sc not in (200, 201):
            send_peer(vk, peer_id=peer_id, text=f"Заявка не создана ({sc}). {format_api_error(sbody)}")
            return
        req_id = int(sbody["id"])
        return_applicant_peer[req_id] = peer_id

        code_me, me_body = api.me(vk_user_id=from_id)
        applicant_name = str(me_body.get("full_name") or "") if code_me == 200 else ""

        notify_text = format_return_notification(
            return_request_id=req_id,
            applicant_name=applicant_name,
            rental_id=int(st.return_rental_id),
            lines_summary=_return_cart_summary(st),
            target_manager=str(mgr.get("full_name") or ""),
        )
        kb = inline_keyboard_two_actions(
            accept_payload=callback_payload_return_decide(req_id, True),
            reject_payload=callback_payload_return_decide(req_id, False),
        )

        mgr_vk = mgr.get("vk_user_id")
        sent = False
        if mgr_vk is not None:
            try:
                send_peer(vk, peer_id=int(mgr_vk), text=notify_text, keyboard=kb)
                sent = True
            except Exception as exc:
                log.warning("notify target manager failed: %s", exc)

        seen: set[int] = set()
        if mgr_vk is not None:
            seen.add(int(mgr_vk))
        for m in st.return_managers:
            vk_uid = m.get("vk_user_id")
            if vk_uid is None:
                continue
            iv = int(vk_uid)
            if iv in seen:
                continue
            seen.add(iv)
            try:
                send_peer(vk, peer_id=iv, text=notify_text, keyboard=kb)
                sent = True
            except Exception as exc:
                log.warning("notify manager vk=%s failed: %s", iv, exc)

        send_peer(
            vk,
            peer_id=peer_id,
            text=f"Заявка на возврат №{req_id} создана." + ("" if sent else " Уведомление завснарам не отправилось."),
        )

        st.flow = None
        st.step = None
        return

    send_peer(vk, peer_id=peer_id, text="Сценарий сбился. Начните снова: /return.")
