"""Сопоставление id заявки с peer_id участника (личка с сообществом), чтобы уведомить после решения завснара."""

from __future__ import annotations

# rental_request_id -> peer_id заявителя
rental_applicant_peer: dict[int, int] = {}
# return_request_id -> peer_id заявителя
return_applicant_peer: dict[int, int] = {}
