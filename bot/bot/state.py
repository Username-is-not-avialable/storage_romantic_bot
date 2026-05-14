from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DialogState:
    """Состояние диалога для peer_id. Любая команда /... сбрасывает сценарий в main."""

    flow: str | None = None  # "issue" | "return" | "link"
    step: str | None = None

    # выдача
    issue_gear_results: list[dict[str, Any]] = field(default_factory=list)
    issue_gear_labels: dict[int, str] = field(default_factory=dict)
    issue_cart: list[tuple[int, int]] = field(default_factory=list)  # gear_id, qty_requested
    issue_managers: list[dict[str, Any]] = field(default_factory=list)
    issue_target_manager_user_id: int | None = None
    issue_event: str | None = None
    issue_due: str | None = None  # дд.мм.гггг
    issue_deposit: str | None = None
    issue_gear_message_ids: dict[int, int] = field(default_factory=dict)  # gear_id -> conversation_message_id
    issue_cart_message_id: int | None = None

    # возврат
    return_rentals: list[dict[str, Any]] = field(default_factory=list)
    return_rental_id: int | None = None
    return_lines: list[dict[str, Any]] = field(default_factory=list)
    return_cart: list[tuple[int, int]] = field(default_factory=list)  # gear_id, qty_return
    return_managers: list[dict[str, Any]] = field(default_factory=list)


_states: dict[int, DialogState] = {}


def get_state(peer_id: int) -> DialogState:
    if peer_id not in _states:
        _states[peer_id] = DialogState()
    return _states[peer_id]


def reset_state(peer_id: int) -> None:
    _states[peer_id] = DialogState()
