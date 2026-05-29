from __future__ import annotations

import vk_api

from bot.api_client import IntegrationClient, format_api_error
from bot.commands import ParsedSlash, parse_slash
from bot.config import vk_link_page_url
from bot.flows.common import LINK_STEP_AWAIT_CODE, help_text, profile_lines
from bot.flows.rental_issue import handle_issue_text, start_issue_flow
from bot.flows.rental_return import handle_return_text, start_return_flow
from bot.state import get_state, reset_state
from bot.vk_send import empty_keyboard, send_peer


def vk_link_instruction_text() -> str:
    page_url = vk_link_page_url()
    if page_url:
        return (
            "Чтобы привязать VK к аккаунту сайта, откройте страницу получения кода:\n"
            f"{page_url}\n\n"
            "Нажмите «Получить код», при необходимости войдите или зарегистрируйтесь, "
            "а затем пришлите полученный код сюда одним сообщением."
        )
    return (
        "Чтобы привязать VK к аккаунту сайта, откройте страницу получения кода на сайте. "
        "Нажмите «Получить код», при необходимости войдите или зарегистрируйтесь, "
        "а затем пришлите полученный код сюда одним сообщением."
    )


def _complete_vk_link(
    vk: vk_api.VkApiMethod,
    api: IntegrationClient,
    *,
    peer_id: int,
    from_id: int,
    code: str,
) -> str:
    """linked — успех; retry — остаёмся в режиме ввода кода; exit — выходим из режима (конфликт и т.п.)."""
    raw = (code or "").strip()
    if not raw:
        send_peer(vk, peer_id=peer_id, text="Код пустой. Пример: /link ABC123")
        return "retry"
    sc, body = api.link_complete(code=raw, vk_user_id=from_id)
    if sc == 200:
        name = body.get("full_name") or "пользователь"
        send_peer(vk, peer_id=peer_id, text=f"Готово. Привязан профиль: {name}.")
        return "linked"
    if sc == 400:
        send_peer(
            vk,
            peer_id=peer_id,
            text="Код недействителен или истёк. Попробуйте снова или запросите новый на сайте.",
        )
        return "retry"
    if sc == 409:
        send_peer(
            vk,
            peer_id=peer_id,
            text=str(body.get("detail", "Этот VK уже привязан к другому пользователю.")),
        )
        return "exit"
    send_peer(vk, peer_id=peer_id, text=f"Ошибка ({sc}). {format_api_error(body)}")
    return "retry"


def handle_slash(
    vk: vk_api.VkApiMethod,
    api: IntegrationClient,
    *,
    peer_id: int,
    from_id: int,
    parsed: ParsedSlash,
) -> None:
    cmd = parsed.verb
    arg = parsed.arg

    if cmd == "start":
        send_peer(vk, peer_id=peer_id, text=help_text(), keyboard=empty_keyboard())
        return

    if cmd == "link":
        if arg:
            _complete_vk_link(vk, api, peer_id=peer_id, from_id=from_id, code=arg)
            return
        st = get_state(peer_id)
        st.flow = "link"
        st.step = LINK_STEP_AWAIT_CODE
        send_peer(
            vk,
            peer_id=peer_id,
            text=vk_link_instruction_text(),
            keyboard=empty_keyboard(),
        )
        return

    if cmd == "profile":
        sc, body = api.me(vk_user_id=from_id)
        if sc == 200:
            send_peer(vk, peer_id=peer_id, text="\n".join(profile_lines(body)), keyboard=empty_keyboard())
        elif sc == 404:
            send_peer(
                vk,
                peer_id=peer_id,
                text=f"Аккаунт VK ещё не привязан. Используйте /link.\n\n{vk_link_instruction_text()}",
                keyboard=empty_keyboard(),
            )
        else:
            send_peer(
                vk,
                peer_id=peer_id,
                text=f"Не удалось загрузить профиль ({sc}). {format_api_error(body)}",
                keyboard=empty_keyboard(),
            )
        return

    if cmd == "issue":
        start_issue_flow(vk, api, peer_id, from_id)
        return

    if cmd == "return":
        start_return_flow(vk, api, peer_id, from_id)
        return

    send_peer(vk, peer_id=peer_id, text="Неизвестная команда. /help — справка.", keyboard=empty_keyboard())


def handle_plain_text(
    vk: vk_api.VkApiMethod,
    api: IntegrationClient,
    *,
    peer_id: int,
    from_id: int,
    text: str,
) -> None:
    st = get_state(peer_id)
    stripped = (text or "").strip()

    if st.flow == "link" and st.step == LINK_STEP_AWAIT_CODE:
        if not stripped:
            send_peer(vk, peer_id=peer_id, text="Пришлите код привязки одной строкой.")
            return
        outcome = _complete_vk_link(vk, api, peer_id=peer_id, from_id=from_id, code=stripped)
        if outcome in ("linked", "exit"):
            st.flow = None
            st.step = None
        return

    if not stripped:
        if st.flow in ("issue", "return"):
            send_peer(vk, peer_id=peer_id, text="Нужен текст (или используйте /help для отмены сценария новой командой).")
        return

    if st.flow == "issue":
        handle_issue_text(vk, api, peer_id, from_id, text)
        return
    if st.flow == "return":
        handle_return_text(vk, api, peer_id, from_id, text)
        return

    send_peer(
        vk,
        peer_id=peer_id,
        text="Нет активного сценария. Команды: /help",
    )


def handle_message_new(
    vk: vk_api.VkApiMethod,
    api: IntegrationClient,
    *,
    peer_id: int,
    from_id: int,
    text: str,
) -> None:
    parsed = parse_slash(text)
    stripped = (text or "").strip()

    if parsed is None and not stripped:
        return

    if parsed is not None:
        reset_state(peer_id)
        handle_slash(vk, api, peer_id=peer_id, from_id=from_id, parsed=parsed)
        return

    handle_plain_text(vk, api, peer_id=peer_id, from_id=from_id, text=text)
