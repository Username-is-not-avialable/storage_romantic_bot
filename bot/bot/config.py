from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise SystemExit(f"Missing required environment variable: {name}")
    return v


def vk_msg_max_len() -> int:
    return int(os.environ.get("VK_BOT_MESSAGE_MAX_LEN", "4000"))


def vk_link_page_url() -> str:
    return os.environ.get("VK_LINK_PAGE_URL", "").strip()
