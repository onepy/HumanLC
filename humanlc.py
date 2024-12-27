# encoding:utf-8
import time
import threading
from datetime import datetime, timedelta
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *


@plugins.register(
    name="HumanLikeChat",
    desire_priority=990,
    desc="Simulates human-like conversation behavior.",
    version="0.1",
    author="YourName",
)
class HumanLikeChat(Plugin):
    def __init__(self):
        super().__init__()
        self.message_cache = []  # 缓存消息列表
        self.message_limit = 20  # 缓存消息数量限制
        self.lock = threading.Lock() # 线程锁，用于保护消息缓存
        self.group_cache = {} # 群聊缓存消息
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[HumanLikeChat] inited")

    def _add_message(self, sender, content, is_group=False):
        with self.lock: # 加锁保护
            timestamp = datetime.now()
            self.message_cache.append({"sender": sender, "content": content, "timestamp": timestamp, "is_group": is_group})
            if len(self.message_cache) > self.message_limit:
                self.message_cache.pop(0)  # 移除最旧的消息

    def _clear_expired_messages(self):
        with self.lock: # 加锁保护
            now = datetime.now()
            self.message_cache = [msg for msg in self.message_cache if now - msg["timestamp"] <= timedelta(hours=1)]

    def _get_cached_messages(self):
        with self.lock: # 加锁保护
            self._clear_expired_messages()
            return self.message_cache.copy()  # 返回消息副本

    def _clear_cache(self, session_id):
        with self.lock:
            if session_id in self.group_cache:
                del self.group_cache[session_id]

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]
        if context.type not in [ContextType.TEXT, ContextType.VOICE]: # 只处理文本和语音消息
            return

        msg = context["msg"]
        sender = msg.from_user_nickname
        content = context.content
        is_group = context.get("isgroup", False)
        session_id = context["session_id"]


        self._add_message(sender, content, is_group)  # 缓存所有消息

        if is_group:
            if not context["msg"].is_at:  # 群聊，非at消息直接缓存
                 if session_id not in self.group_cache:
                     self.group_cache[session_id] = []
                 self.group_cache[session_id].append({"sender": sender, "content": content, "timestamp": datetime.now()})
                 e_context.action = EventAction.BREAK_PASS  # 不往下传递给其他插件，直接结束
                 return
            else: # 群聊，at消息，则提取缓存消息给gpt
                if session_id in self.group_cache:
                    cached_messages = self.group_cache.get(session_id)
                    prompt = ""
                    for message in cached_messages:
                         prompt += f"{message['sender']}: {message['content']}
"
                    prompt += f"{sender}：{content}"
                    context.content = prompt
                    self._clear_cache(session_id)
                else:
                    return
        # 私聊信息直接发送给gpt
        e_context.action = EventAction.CONTINUE

    def get_help_text(self, **kwargs):
        return "Simulates human-like conversation behavior with message caching."
