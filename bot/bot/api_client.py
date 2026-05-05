from __future__ import annotations

import json
from typing import Any

import httpx

from bot.config import require_env


class IntegrationClient:
    """HTTP-клиент к API: публичные GET и integration с X-VK-Bot-Secret + vk_user_id."""

    def __init__(self) -> None:
        self._base = require_env("API_BASE_URL").rstrip("/")
        self._secret = require_env("VK_BOT_SECRET")
        self._client = httpx.Client(timeout=60.0)

    def close(self) -> None:
        self._client.close()

    def _int_headers(self) -> dict[str, str]:
        return {"X-VK-Bot-Secret": self._secret}

    @staticmethod
    def _json(r: httpx.Response) -> dict[str, Any]:
        try:
            body = r.json()
            return body if isinstance(body, dict) else {"_raw": body}
        except Exception:
            return {}

    def get_gear(self, *, query: str, limit: int = 15) -> tuple[int, dict[str, Any]]:
        r = self._client.get(
            f"{self._base}/api/gear/",
            params={"query": query, "limit": limit, "page": 1},
        )
        return r.status_code, self._json(r)

    def link_complete(self, *, code: str, vk_user_id: int) -> tuple[int, dict[str, Any]]:
        r = self._client.post(
            f"{self._base}/api/integrations/vk/link-complete",
            json={"code": code, "vk_user_id": vk_user_id},
            headers=self._int_headers(),
        )
        return r.status_code, self._json(r)

    def me(self, *, vk_user_id: int) -> tuple[int, dict[str, Any]]:
        r = self._client.get(
            f"{self._base}/api/integrations/vk/me",
            params={"vk_user_id": vk_user_id},
            headers=self._int_headers(),
        )
        return r.status_code, self._json(r)

    def managers(self) -> tuple[int, dict[str, Any]]:
        r = self._client.get(
            f"{self._base}/api/integrations/vk/managers",
            headers=self._int_headers(),
        )
        return r.status_code, self._json(r)

    def active_rentals(self, *, vk_user_id: int) -> tuple[int, dict[str, Any]]:
        r = self._client.get(
            f"{self._base}/api/integrations/vk/rentals/active",
            params={"vk_user_id": vk_user_id},
            headers=self._int_headers(),
        )
        return r.status_code, self._json(r)

    def post_rental_request(
        self, *, vk_user_id: int, body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        r = self._client.post(
            f"{self._base}/api/integrations/vk/rental-requests",
            params={"vk_user_id": vk_user_id},
            json=body,
            headers=self._int_headers(),
        )
        return r.status_code, self._json(r)

    def post_return_request(
        self, *, vk_user_id: int, body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        r = self._client.post(
            f"{self._base}/api/integrations/vk/rental-return-requests",
            params={"vk_user_id": vk_user_id},
            json=body,
            headers=self._int_headers(),
        )
        return r.status_code, self._json(r)

    def decide_rental_request(
        self,
        *,
        manager_vk_user_id: int,
        rental_request_id: int,
        decision: str,
        comment: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        r = self._client.patch(
            f"{self._base}/api/integrations/vk/manager/rental-requests/{rental_request_id}",
            params={"vk_user_id": manager_vk_user_id},
            json={"decision": decision, "comment": comment},
            headers=self._int_headers(),
        )
        return r.status_code, self._json(r)

    def decide_return_request(
        self,
        *,
        manager_vk_user_id: int,
        return_request_id: int,
        decision: str,
        comment: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        r = self._client.patch(
            f"{self._base}/api/integrations/vk/manager/rental-return-requests/{return_request_id}",
            params={"vk_user_id": manager_vk_user_id},
            json={"decision": decision, "comment": comment},
            headers=self._int_headers(),
        )
        return r.status_code, self._json(r)


def format_api_error(body: dict[str, Any]) -> str:
    detail = body.get("detail")
    if isinstance(detail, list):
        parts = []
        for x in detail:
            if isinstance(x, dict) and "msg" in x:
                parts.append(str(x["msg"]))
            else:
                parts.append(str(x))
        return "; ".join(parts)
    if detail is not None:
        return str(detail)
    return json.dumps(body, ensure_ascii=False)[:500]
