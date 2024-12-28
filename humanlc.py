import plugins
from common.log import logger
from plugins import *
from bridge.context import ContextType
from datetime import datetime, timedelta

@plugins.register(name="humanlc", desc="A simple plugin that caches and outputs recent group messages", version="0.3", author="Pon")
class humanlc(Plugin):
    def __init__(self):
        super().__init__()
        self.message_cache = []
        self.max_cache_size = 30
        self.max_message_age = timedelta(hours=1)
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[humanlc] inited")

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type != ContextType.TEXT:
          return

        msg = e_context['context']['msg']
        if not e_context['context'].get("isgroup", False):
          return

        # 群聊消息缓存
        if msg and msg.from_user_id and msg.content:
          self.cache_message(msg.actual_user_nickname, msg.content)

        # 清理过期消息
        self.cleanup_expired_messages()

        # 如果被艾特,拼接消息
        if e_context['context'].get("isgroup",False) and msg.is_at:
            cached_messages = self.get_cached_messages()
            if cached_messages:
                e_context['context'].content = "
".join(cached_messages)
                logger.debug(f"[humanlc] Cached messages: 
{e_context['context'].content}")
            else:
                logger.debug(f"[humanlc] No cached messages")

        e_context.action = EventAction.CONTINUE 
        return

    def cache_message(self, sender, content):
        timestamp = datetime.now()
        self.message_cache.append({"sender": sender, "content": content, "timestamp": timestamp})
        if len(self.message_cache) > self.max_cache_size:
            self.message_cache.pop(0)

    def cleanup_expired_messages(self):
        now = datetime.now()
        self.message_cache = [
            msg for msg in self.message_cache
            if now - msg["timestamp"] <= self.max_message_age
        ]
        logger.debug(f"[humanlc] clean cache, current size:{len(self.message_cache)}")

    def get_cached_messages(self):
        return [f"{msg['sender']}: {msg['content']}" for msg in self.message_cache]
