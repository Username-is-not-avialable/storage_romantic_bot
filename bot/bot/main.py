from __future__ import annotations

import logging

import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll

from bot.api_client import IntegrationClient
from bot.callbacks import handle_message_event
from bot.config import configure_logging, require_env
from bot.flows.conversation import handle_message_new

log = logging.getLogger(__name__)


def main() -> None:
    configure_logging()

    token = require_env("VK_GROUP_TOKEN")
    group_id = int(require_env("VK_GROUP_ID"))

    vk_session = vk_api.VkApi(token=token)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id=group_id)

    log.info("VK Long Poll started for group_id=%s", group_id)

    api = IntegrationClient()
    try:
        for event in longpoll.listen():
            try:
                if event.type == VkBotEventType.MESSAGE_NEW:
                    if getattr(event, "from_chat", False) or getattr(event, "from_group", False):
                        continue
                    msg = event.message
                    if not msg:
                        continue
                    text = msg.get("text") or ""
                    peer_id = int(msg["peer_id"])
                    from_id = int(msg.get("from_id") or peer_id)
                    handle_message_new(vk, api, peer_id=peer_id, from_id=from_id, text=text)
                    continue

                if event.type == VkBotEventType.MESSAGE_EVENT:
                    handle_message_event(vk, api, event)
                    continue
            except Exception as exc:
                log.exception("handler error: %s", exc)
    finally:
        api.close()


if __name__ == "__main__":
    main()
