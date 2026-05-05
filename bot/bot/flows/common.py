"""Общие тексты и форматирование."""

from __future__ import annotations


LINK_STEP_AWAIT_CODE = "link_code"


def help_text() -> str:
    return (
        "Команды (через /):\n"
        "/start или /help — справка\n"
        "/link или /привязать <код> — связать VK с сайтом (или /link и код следующим сообщением)\n"
        "/profile или /профиль — ваш профиль\n\n"
        "Для участников, менеджеров и администраторов:\n"
        "/issue или /выдача — заявка на получение снаряжения\n"
        "/return или /возврат — заявка на возврат\n\n"
        "Код привязки выдаётся на сайте после входа в аккаунт."
    )


def profile_lines(me_body: dict) -> list[str]:
    lines = [
        f"Имя: {me_body.get('full_name', '')}",
        f"Email: {me_body.get('email', '')}",
        f"Телефон: {me_body.get('phone', '')}",
        f"Роль: {me_body.get('role', '')}",
    ]
    if me_body.get("document"):
        lines.append(f"Документ: {me_body['document']}")
    return lines
