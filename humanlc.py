import time
from collections import deque
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *


@plugins.register(
    name="humanlc",
    desire_priority=950,
    desc="Simulates human conversation behavior.",
    version="0.1",
    author="Your Name",
)
class humanlc(Plugin):
    def __init__(self):
        super().__init__()
        self.message_cache = deque(maxlen=20)  # 缓存最近的20条消息
        self.group_message_cache = {}  # 群聊消息缓存，key为group_id
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.last_cleanup_time = time.time()
        logger.info("[HumanLikeChat] inited")
        self.cleanup_interval = 300  # 5分钟清理一次过期缓存

    def _cleanup_expired_messages(self):
        """清除过期消息"""
        now = time.time()
        
        
        # 清理通用消息缓存
        while self.message_cache and now - self.message_cache[0]["timestamp"] > 3600:
            self.message_cache.popleft()
        
        # 清理群聊消息缓存
        expired_groups = []
        for group_id, messages in self.group_message_cache.items():
            while messages and now - messages[0]["timestamp"] > 3600:
               messages.pop(0)
            if not messages:
                 expired_groups.append(group_id)
        for group_id in expired_groups:
              del self.group_message_cache[group_id]


    def on_handle_context(self, e_context: EventContext):
        # 每隔一段时间清除过期消息
        if time.time() - self.last_cleanup_time > self.cleanup_interval:
            self._cleanup_expired_messages()
            self.last_cleanup_time = time.time()
        
        context = e_context["context"]
        msg = context.get("msg")
        if not msg:
            return

        is_group = context.get("isgroup", False)

        message_info = {
            "sender": msg.from_user_nickname,
            "content": context.content,
            "timestamp": time.time(),
            "is_group": is_group,
            "actual_user_id": msg.actual_user_id,
        }
        self.message_cache.append(message_info)

        if is_group:  # 群聊消息处理
            group_id = msg.other_user_id
            if group_id not in self.group_message_cache:
                self.group_message_cache[group_id] = []
            self.group_message_cache[group_id].append(message_info)

            if not msg.is_at:
                logger.debug(
                    f"[HumanLikeChat] Group message cached, not at bot, group_id={group_id}, content={context.content}"
                )
                e_context.action = EventAction.BREAK_PASS  # 不发送给GPT
            else:
                # @ 机器人
                logger.debug(
                    f"[HumanLikeChat] Group message at bot, group_id={group_id}, content={context.content}"
                )
                # 获取群聊缓存的消息，拼接后发送给 GPT
                if group_id in self.group_message_cache:
                  group_messages = self.group_message_cache.get(group_id,[])
                  context.content = "
".join(
                      [f"{m['sender']}: {m['content']}" for m in group_messages]
                  )
                  del self.group_message_cache[group_id]
                  
        else:
            # 私聊消息直接发送给GPT
             logger.debug(
                    f"[HumanLikeChat] Private message, content={context.content}"
                )

        e_context.action = EventAction.CONTINUE

    def get_help_text(self, **kwargs):
        return "Simulates human-like chat behavior, including caching messages and delayed responses in groups."
