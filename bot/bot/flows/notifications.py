from __future__ import annotations


def callback_payload_rental_decide(rental_request_id: int, approve: bool) -> dict[str, str | int]:
    """Компактный JSON для callback VK (лимит payload)."""
    return {"t": "rq", "i": rental_request_id, "d": "a" if approve else "r"}


def callback_payload_return_decide(return_request_id: int, approve: bool) -> dict[str, str | int]:
    return {"t": "rt", "i": return_request_id, "d": "a" if approve else "r"}


def format_rental_notification(
    *,
    rental_request_id: int,
    applicant_name: str,
    event: str,
    due_date: str,
    cart_summary: str,
    deposit: str | None,
    comment: str | None,
    preferred_manager: str,
) -> str:
    lines = [
        f"Заявка на выдачу №{rental_request_id}",
        f"Участник: {applicant_name or '—'}",
        f"Приоритетный завснар: {preferred_manager or '—'}",
        f"Мероприятие: {event}",
        f"Срок возврата: {due_date}",
        "Позиции:",
        cart_summary,
    ]
    if deposit:
        lines.append(f"Документ: {deposit}")
    if comment:
        lines.append(f"Комментарий: {comment}")
    lines.append("")
    lines.append("Принять или отклонить:")
    return "\n".join(lines)


def format_return_notification(
    *,
    return_request_id: int,
    applicant_name: str,
    rental_id: int,
    lines_summary: str,
    target_manager: str,
) -> str:
    return (
        f"Заявка на возврат №{return_request_id}\n"
        f"Участник: {applicant_name or '—'}\n"
        f"Аренда (rental_id): {rental_id}\n"
        f"Завснар (адресат): {target_manager or '—'}\n"
        f"Позиции:\n{lines_summary}\n\n"
        "Принять или отклонить:"
    )


def rental_decision_member_text(*, approved: bool, detail: str | None, req_id: int) -> str:
    if approved:
        return f"Заявка №{req_id} одобрена завснаром.{(' ' + detail) if detail else ''}"
    return f"Заявка №{req_id} отклонена.{(' Причина: ' + detail) if detail else ''}"


def return_decision_member_text(*, approved: bool, detail: str | None, req_id: int) -> str:
    if approved:
        return f"Заявка на возврат №{req_id} принята.{(' ' + detail) if detail else ''}"
    return f"Заявка на возврат №{req_id} отклонена.{(' ' + detail) if detail else ''}"
