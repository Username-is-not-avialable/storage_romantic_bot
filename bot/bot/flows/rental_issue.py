from __future__ import annotations

import logging
import re
from typing import Any

import vk_api

from bot.api_client import IntegrationClient, format_api_error
from bot.notify_registry import rental_applicant_peer
from bot.state import DialogState, get_state
from bot.vk_send import (
    inline_keyboard_issue_qty,
    inline_keyboard_two_actions,
    keyboard_issue_actions,
    send_peer,
)

from .notifications import callback_payload_rental_decide, format_rental_notification

log = logging.getLogger(__name__)

ISSUE_SEARCH = "issue_search"
ISSUE_ADD = "issue_add"
ISSUE_EVENT = "issue_event"
ISSUE_DATE = "issue_date"
ISSUE_DOC = "issue_doc"
ISSUE_MANAGER = "issue_manager"
ISSUE_COMMENT = "issue_comment"

_DONE = frozenset({"готово", "done", "далее"})
_SKIP = frozenset({"пропустить", "skip", "-", "нет", "no"})
DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


def _merge_cart(cart: list[tuple[int, int]]) -> list[dict[str, int]]:
    m: dict[int, int] = {}
    for gid, q in cart:
        m[gid] = m.get(gid, 0) + q
    return [{"gear_id": g, "qty_requested": q} for g, q in sorted(m.items())]


def _cart_summary(st: DialogState) -> str:
    lines = []
    merged = _merge_cart(st.issue_cart)
    for it in merged:
        gid = it["gear_id"]
        name = st.issue_gear_labels.get(gid, f"id {gid}")
        lines.append(f"• {name} ×{it['qty_requested']}")
    return "\n".join(lines) if lines else "(пусто)"


def issue_gear_payload(*, gear_id: int, delta: int) -> dict[str, Any]:
    return {"t": "ig", "g": int(gear_id), "d": int(delta)}


def _issue_show_gear_results(
    vk: vk_api.VkApiMethod,
    api: IntegrationClient,
    peer_id: int,
    st: DialogState,
    raw_query: str,
) -> None:
    gc, gbody = api.get_gear(query=raw_query, limit=15)
    if gc != 200:
        send_peer(vk, peer_id=peer_id, text=f"Поиск не удался ({gc}). {format_api_error(gbody)}")
        return
    items = list(gbody.get("items") or [])
    if not items:
        send_peer(vk, peer_id=peer_id, text="Ничего не найдено. Попробуйте другой запрос.")
        return
    st.issue_gear_results = items
    for it in items:
        gid = int(it["id"])
        st.issue_gear_labels[gid] = str(it.get("name") or f"id {gid}")
    lines = [f"Результаты по запросу «{raw_query}». Нажимайте +/- у каждой позиции:"]
    send_peer(vk, peer_id=peer_id, text="\n".join(lines))
    st.issue_gear_message_ids.clear()
    for i, it in enumerate(items, start=1):
        gid = int(it["id"])
        avail = int(it.get("available_count") or 0)
        text = f"{i}. {it.get('name')} — свободно {avail}"
        kb = inline_keyboard_issue_qty(
            minus_payload=issue_gear_payload(gear_id=gid, delta=-1),
            plus_payload=issue_gear_payload(gear_id=gid, delta=1),
        )
        cmid = send_peer(vk, peer_id=peer_id, text=text, keyboard=kb)
        if cmid is not None:
            st.issue_gear_message_ids[gid] = cmid

    cart_text = "Текущая корзина:\n" + _cart_summary(st)
    st.issue_cart_message_id = send_peer(vk, peer_id=peer_id, text=cart_text, keyboard=keyboard_issue_actions())
    st.step = ISSUE_ADD


def start_issue_flow(vk: vk_api.VkApiMethod, api: IntegrationClient, peer_id: int, from_id: int) -> None:
    st = get_state(peer_id)
    code, me_body = api.me(vk_user_id=from_id)
    if code == 404:
        send_peer(vk, peer_id=peer_id, text="Сначала привяжите аккаунт: /link и код с сайта.")
        return
    if code != 200:
        send_peer(
            vk,
            peer_id=peer_id,
            text=f"Не удалось проверить профиль ({code}). {format_api_error(me_body)}",
        )
        return
    if me_body.get("role") not in {"member", "manager", "admin"}:
        send_peer(
            vk,
            peer_id=peer_id,
            text="Заявку на выдачу через бот могут оформить участники, менеджеры и администраторы.",
        )
        return
    mc, mbody = api.managers()
    if mc != 200:
        send_peer(
            vk,
            peer_id=peer_id,
            text=f"Не удалось загрузить завснаров ({mc}). {format_api_error(mbody)}",
        )
        return
    managers = list(mbody.get("managers") or [])
    vk_managers = [m for m in managers if m.get("vk_user_id")]
    if not vk_managers:
        send_peer(
            vk,
            peer_id=peer_id,
            text="Ни у одного завснара не привязан VK — обработать заявку из бота некому. Обратитесь к администратору.",
        )
        return

    st.flow = "issue"
    st.step = ISSUE_SEARCH
    st.issue_managers = vk_managers
    st.issue_cart.clear()
    st.issue_gear_results.clear()
    st.issue_gear_labels.clear()
    st.issue_target_manager_user_id = None
    st.issue_event = None
    st.issue_due = None
    st.issue_deposit = None

    send_peer(
        vk,
        peer_id=peer_id,
        text=(
            "Заявка на выдачу.\n"
            "Шаг 1: введите не менее 3 символов для поиска снаряжения на складе "
            "(название или часть описания)."
        ),
    )


def handle_issue_text(
    vk: vk_api.VkApiMethod,
    api: IntegrationClient,
    peer_id: int,
    from_id: int,
    text: str,
) -> None:
    st = get_state(peer_id)
    assert st.flow == "issue"
    raw = (text or "").strip()
    low = raw.lower()

    if st.step == ISSUE_SEARCH:
        if len(raw) < 3:
            send_peer(vk, peer_id=peer_id, text="Запрос слишком короткий — минимум 3 символа.")
            return
        _issue_show_gear_results(vk, api, peer_id, st, raw)
        return

    if st.step == ISSUE_ADD:
        if low in {"посмотреть корзину", "корзина"}:
            send_peer(vk, peer_id=peer_id, text="Текущая корзина:\n" + _cart_summary(st), keyboard=keyboard_issue_actions())
            return
        if low in {"новый поиск", "поиск"}:
            st.step = ISSUE_SEARCH
            send_peer(vk, peer_id=peer_id, text="Введите новый поисковый запрос (не короче 3 символов).", keyboard=keyboard_issue_actions())
            return
        if low in _DONE:
            if not st.issue_cart:
                send_peer(vk, peer_id=peer_id, text="Корзина пуста — сначала добавьте позиции кнопками +.")
                return
            st.step = ISSUE_EVENT
            send_peer(
                vk,
                peer_id=peer_id,
                text=("Корзина:\n" + _cart_summary(st) + "\n\nШаг 3: укажите мероприятие одной строкой (до 100 символов)."),
            )
            return
        if len(raw) < 3:
            send_peer(
                vk,
                peer_id=peer_id,
                text="Используйте кнопки +/− у позиций, либо нажмите «Новый поиск», «Посмотреть корзину» или «Готово».",
            )
            return
        _issue_show_gear_results(vk, api, peer_id, st, raw)
        return

    if st.step == ISSUE_EVENT:
        if len(raw) > 100:
            send_peer(vk, peer_id=peer_id, text="Слишком длинно — максимум 100 символов для мероприятия.")
            return
        if not raw:
            send_peer(vk, peer_id=peer_id, text="Введите название мероприятия.")
            return
        st.issue_event = raw
        st.step = ISSUE_DATE
        send_peer(vk, peer_id=peer_id, text="Шаг 4: срок возврата в формате дд.мм.гггг")
        return

    if st.step == ISSUE_DATE:
        if not DATE_RE.match(raw):
            send_peer(vk, peer_id=peer_id, text="Дата должна быть строго в формате дд.мм.гггг.")
            return
        st.issue_due = raw
        st.step = ISSUE_DOC
        send_peer(
            vk,
            peer_id=peer_id,
            text="Шаг 5: наименование залогового документа одной строкой",
        )
        return

    if st.step == ISSUE_DOC:
        if low in _SKIP:
            st.issue_deposit = None
        else:
            if len(raw) > 300:
                send_peer(vk, peer_id=peer_id, text="Слишком длинно для поля документа (макс. 300 символов).")
                return
            st.issue_deposit = raw
        st.step = ISSUE_MANAGER
        lines = ["Шаг 6: выберите завснара, которому уйдёт заявка (уведомление в VK только ему). Номер из списка:"]
        for i, m in enumerate(st.issue_managers, start=1):
            lines.append(f"{i}. {m.get('full_name')} ({m.get('role')})")
        send_peer(vk, peer_id=peer_id, text="\n".join(lines))
        return

    if st.step == ISSUE_MANAGER:
        try:
            n = int(raw)
        except ValueError:
            send_peer(vk, peer_id=peer_id, text="Ответьте номером из списка.")
            return
        if n < 1 or n > len(st.issue_managers):
            send_peer(vk, peer_id=peer_id, text="Номер вне списка.")
            return
        st.issue_target_manager_user_id = int(st.issue_managers[n - 1]["user_id"])
        st.step = ISSUE_COMMENT
        send_peer(
            vk,
            peer_id=peer_id,
            text="Шаг 7 (необязательно): комментарий к заявке или «пропустить».",
        )
        return

    if st.step == ISSUE_COMMENT:
        comment: str | None
        if low in _SKIP:
            comment = None
        else:
            if len(raw) > 500:
                send_peer(vk, peer_id=peer_id, text="Комментарий не длиннее 500 символов.")
                return
            comment = raw

        items_payload = _merge_cart(st.issue_cart)
        body: dict[str, Any] = {
            "due_date": st.issue_due,
            "event": st.issue_event,
            "comment": comment,
            "deposit_document": st.issue_deposit,
            "items": items_payload,
            "target_manager_id": int(st.issue_target_manager_user_id or 0),
        }
        sc, sbody = api.post_rental_request(vk_user_id=from_id, body=body)
        if sc not in (200, 201):
            send_peer(vk, peer_id=peer_id, text=f"Заявка не создана ({sc}). {format_api_error(sbody)}")
            return
        req_id = int(sbody["id"])
        rental_applicant_peer[req_id] = peer_id

        mgr_name = ""
        for m in st.issue_managers:
            if int(m["user_id"]) == int(st.issue_target_manager_user_id or 0):
                mgr_name = str(m.get("full_name") or "")
                break

        send_peer(
            vk,
            peer_id=peer_id,
            text=(
                f"Заявка №{req_id} отправлена (ожидает решения).\n"
                f"Адресат: {mgr_name or st.issue_target_manager_user_id}.\n"
                "Ему придёт уведомление в VK."
            ),
        )

        code_me, me_body = api.me(vk_user_id=from_id)
        applicant_name = str(me_body.get("full_name") or "") if code_me == 200 else ""

        notify_text = format_rental_notification(
            rental_request_id=req_id,
            applicant_name=applicant_name,
            event=str(st.issue_event),
            due_date=str(st.issue_due),
            cart_summary=_cart_summary(st),
            deposit=st.issue_deposit,
            comment=comment,
            preferred_manager=mgr_name,
        )
        kb = inline_keyboard_two_actions(
            accept_payload=callback_payload_rental_decide(req_id, True),
            reject_payload=callback_payload_rental_decide(req_id, False),
        )

        target_vk: int | None = None
        for m in st.issue_managers:
            if int(m["user_id"]) == int(st.issue_target_manager_user_id or 0):
                v = m.get("vk_user_id")
                if v is not None:
                    target_vk = int(v)
                break

        if target_vk is None:
            send_peer(
                vk,
                peer_id=peer_id,
                text="Заявка создана, но у выбранного завснара нет привязки VK — уведомление не отправлено.",
            )
        else:
            try:
                send_peer(vk, peer_id=target_vk, text=notify_text, keyboard=kb)
            except Exception as exc:
                log.warning("notify target manager vk=%s failed: %s", target_vk, exc)
                send_peer(
                    vk,
                    peer_id=peer_id,
                    text="Заявка создана, но отправить уведомление в VK не удалось.",
                )

        st.flow = None
        st.step = None
        return

    send_peer(vk, peer_id=peer_id, text="Внутренняя ошибка шага сценария. Начните заново: /issue.")
