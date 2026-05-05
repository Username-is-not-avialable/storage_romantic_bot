from __future__ import annotations

import logging
from typing import Any

import vk_api

from bot.api_client import IntegrationClient, format_api_error
from bot.notify_registry import return_applicant_peer
from bot.state import DialogState, get_state
from bot.vk_send import inline_keyboard_two_actions, send_peer

from .notifications import callback_payload_return_decide, format_return_notification

log = logging.getLogger(__name__)

RETURN_PICK_RENTAL = "return_rental"
RETURN_PICK_ITEMS = "return_items"
RETURN_PICK_MANAGER = "return_manager"

_DONE = frozenset({"готово", "done", "далее"})


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
    send_peer(vk, peer_id=peer_id, text="\n".join(lines))


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
        lines = [f"Аренда №{st.return_rental_id}: введите номер и количество через пробел, либо «готово», если всё выбрали."]
   
        for i, it in enumerate(items, start=1):
            gid = it.get("gear_id")
            nm = it.get("gear_name", "")
            out = it.get("qty_outstanding", 0)
            lines.append(f"{i}. {nm} (gear_id {gid}) — к возврату до {out} шт.")
        lines.append("Когда выбрано всё — напишите «готово».")
        st.step = RETURN_PICK_ITEMS
        send_peer(vk, peer_id=peer_id, text="\n".join(lines))
        return

    if st.step == RETURN_PICK_ITEMS:
        if low in _DONE:
            if not st.return_cart:
                send_peer(vk, peer_id=peer_id, text="Выберите хотя бы одну позицию.")
                return
            st.step = RETURN_PICK_MANAGER
            mlines = ["Кому сдавать (target_manager_id). Выберите номер завснара:"]
            for i, m in enumerate(st.return_managers, start=1):
                mlines.append(f"{i}. {m.get('full_name')} ({m.get('role')})")
            send_peer(vk, peer_id=peer_id, text="\n".join(mlines))
            return
        parts = raw.split()
        if len(parts) != 2:
            send_peer(vk, peer_id=peer_id, text="Формат: номер_строки количество (например: 1 1).")
            return
        try:
            idx = int(parts[0])
            qty = int(parts[1])
        except ValueError:
            send_peer(vk, peer_id=peer_id, text="Ожидаются два целых числа.")
            return
        if idx < 1 or idx > len(st.return_lines):
            send_peer(vk, peer_id=peer_id, text="Номер строки не из списка.")
            return
        if qty <= 0:
            send_peer(vk, peer_id=peer_id, text="Количество должно быть больше нуля.")
            return
        line = st.return_lines[idx - 1]
        gid = int(line["gear_id"])
        max_q = int(line.get("qty_outstanding") or 0)
        already = sum(q for g, q in st.return_cart if g == gid)
        if already + qty > max_q:
            send_peer(
                vk,
                peer_id=peer_id,
                text=f"Слишком много для этой позиции (максимум к возврату {max_q}, уже в черновике {already}).",
            )
            return
        st.return_cart.append((gid, qty))
        send_peer(
            vk,
            peer_id=peer_id,
            text=("Добавлено.\nЧерновик возврата:\n" + _return_cart_summary(st) + "\n\nЕщё позиции или «готово»."),
        )
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
