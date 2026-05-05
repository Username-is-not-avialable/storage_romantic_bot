from __future__ import annotations

import logging
import re
from typing import Any

import vk_api

from bot.api_client import IntegrationClient, format_api_error
from bot.notify_registry import rental_applicant_peer
from bot.state import DialogState, get_state
from bot.vk_send import inline_keyboard_two_actions, send_peer

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


def _hint_issue_step2_more_items() -> str:
    return "Введите номер и количество через пробел, либо название другого снаряжения, либо «готово», если всё выбрали."


def _instructions_issue_step2_after_search() -> tuple[str, str]:
    """Две строки под списком находок: как выбрать из списка; как искать дальше и закончить."""
    return (
        "Шаг 2. Чтобы взять позицию из списка выше, отправьте два числа через пробел: сначала номер строки, "
        "потом сколько штук нужно. Например, 1 2 — первая строка, две штуки.",
        "Нужна другая вещь — наберите новый поисковый запрос (не короче 3 символов). Когда всё выбрали — «готово».",
    )


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
    lines = [f'По запросу «{raw_query}»:']
    for i, it in enumerate(items, start=1):
        avail = it.get("available_count", "?")
        lines.append(f"{i}. {it.get('name')} — свободно {avail} (id {it['id']})")
    lines.append("")
    pick, footer = _instructions_issue_step2_after_search()
    lines.append(pick)
    lines.append(footer)
    st.step = ISSUE_ADD
    send_peer(vk, peer_id=peer_id, text="\n".join(lines))


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
        if low in _DONE:
            if not st.issue_cart:
                send_peer(vk, peer_id=peer_id, text="Корзина пуста — сначала добавьте позиции номером и количеством.")
                return
            st.step = ISSUE_EVENT
            send_peer(
                vk,
                peer_id=peer_id,
                text=("Корзина:\n" + _cart_summary(st) + "\n\nШаг 3: укажите мероприятие одной строкой (до 100 символов)."),
            )
            return
        parts = raw.split()
        idx: int | None = None
        qty: int | None = None
        if len(parts) == 2:
            try:
                idx = int(parts[0])
                qty = int(parts[1])
            except ValueError:
                idx = qty = None
        if idx is not None and qty is not None:
            if idx < 1 or idx > len(st.issue_gear_results):
                send_peer(vk, peer_id=peer_id, text="Номер позиции не из списка.")
                return
            if qty <= 0:
                send_peer(vk, peer_id=peer_id, text="Количество должно быть больше нуля.")
                return
            gear = st.issue_gear_results[idx - 1]
            gid = int(gear["id"])
            avail = int(gear.get("available_count") or 0)
            if qty > avail:
                send_peer(vk, peer_id=peer_id, text=f"Доступно только {avail} шт. для «{gear.get('name')}».")
                return
            st.issue_cart.append((gid, qty))
            send_peer(
                vk,
                peer_id=peer_id,
                text=(
                    "Добавлено.\nТекущая корзина:\n"
                    + _cart_summary(st)
                    + "\n\n"
                    + _hint_issue_step2_more_items()
                ),
            )
            return

        if len(raw) < 3:
            send_peer(
                vk,
                peer_id=peer_id,
                text=(
                    "Ожидаю «номер количество» из текущего списка (например: 1 2), "
                    "или новый поиск не короче 3 символов, или «готово»."
                ),
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
        lines = ["Шаг 6: кому адресовать заявку (ответят все завснары с привязкой VK). Выберите номер:"]
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
                f"Вы указали адресата: {mgr_name or st.issue_target_manager_user_id}.\n"
                "Завснары получат уведомление в VK."
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
        sent_any = False
        seen_vk: set[int] = set()
        for m in st.issue_managers:
            vk_uid = m.get("vk_user_id")
            if vk_uid is None:
                continue
            iv = int(vk_uid)
            if iv in seen_vk:
                continue
            seen_vk.add(iv)
            try:
                send_peer(vk, peer_id=iv, text=notify_text, keyboard=kb)
                sent_any = True
            except Exception as exc:
                log.warning("notify manager vk=%s failed: %s", iv, exc)
        if not sent_any:
            send_peer(
                vk,
                peer_id=peer_id,
                text="Заявка создана, но отправить уведомление завснарам не удалось.",
            )

        st.flow = None
        st.step = None
        return

    send_peer(vk, peer_id=peer_id, text="Внутренняя ошибка шага сценария. Начните заново: /issue.")
