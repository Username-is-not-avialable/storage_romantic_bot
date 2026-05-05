"""Разбор команд Telegram-стиля: /команда и алиасы."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedSlash:
    verb: str
    arg: str | None


_VERB_TO_INTERNAL: dict[str, str] = {
    # start / help
    "start": "start",
    "старт": "start",
    "help": "start",
    "хелп": "start",
    # link
    "link": "link",
    "привязать": "link",
    # profile
    "profile": "profile",
    "профиль": "profile",
    "me": "profile",
    "я": "profile",
    # issue rental
    "issue": "issue",
    "выдача": "issue",
    "получить": "issue",
    "rent": "issue",
    "аренда": "issue",
    # return
    "return": "return",
    "возврат": "return",
    "сдать": "return",
}


def parse_slash(text: str) -> ParsedSlash | None:
    t = (text or "").strip()
    if not t.startswith("/"):
        return None
    rest = t[1:].strip()
    if not rest:
        return None
    m = re.match(r"(\S+)(?:\s+(.*))?", rest, re.DOTALL)
    if not m:
        return None
    raw_verb = (m.group(1) or "").lower()
    arg = (m.group(2) or "").strip() or None
    verb = _VERB_TO_INTERNAL.get(raw_verb, raw_verb)
    return ParsedSlash(verb=verb, arg=arg)


def is_slash_command(text: str) -> bool:
    return parse_slash(text) is not None
