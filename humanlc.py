# encoding: utf-8

import threading
import time
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *

@plugins.register(
    name="HumanLC",
    desire_priority=500,  # 设置较高的优先级，确保在其他插件之前拦截消息
    hidden=False,
    desc="A plugin that intercepts private chat messages and concatenates them before passing to the next step. Includes a timeout mechanism.",
    version="0.3",
    author="YourName",
)
class HumanLC(Plugin):
    def __init__(self):
        super().__init__()
        self.intercept_count = 5  # 拦截次数
        self.intercepted_messages = {}  # 用于存储拦截的消息
        self.timers = {}  # 用于存储每个会话的超时计时器
        self.timeout = 10  # 超时时间，单位为秒
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[HumanLC] inited")

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]

        # 只拦截私聊消息
        if not context.get("isgroup", False):
            session_id = context["session_id"]
            content = context.content

            # 如果当前会话还没有计时器，创建一个
            if session_id not in self.timers:
                self.timers[session_id] = threading.Timer(self.timeout, self.timeout_handler, args=[session_id, e_context])
                self.timers[session_id].start()

            if session_id not in self.intercepted_messages:
                self.intercepted_messages[session_id] = []

            self.intercepted_messages[session_id].append(content)

            # 重置计时器
            self.timers[session_id].cancel()
            self.timers[session_id] = threading.Timer(self.timeout, self.timeout_handler, args=[session_id, e_context])
            self.timers[session_id].start()

            # 拦截次数达到5次时，拼接消息并继续处理
            if len(self.intercepted_messages[session_id]) >= self.intercept_count:
                self.timers[session_id].cancel()  # 取消计时器
                self.process_intercepted_messages(session_id, e_context)
            else:
                e_context.action = EventAction.BREAK_PASS  # 拦截消息，不继续处理
        else:
            e_context.action = EventAction.CONTINUE  # 群聊消息正常处理

    def timeout_handler(self, session_id, e_context):
        """超时处理函数，触发时将当前拦截的消息发送给后续插件或默认消息处理逻辑"""
        if session_id in self.intercepted_messages and len(self.intercepted_messages[session_id]) > 0:
            self.process_intercepted_messages(session_id, e_context)

    def process_intercepted_messages(self, session_id, e_context):
        """处理拦截的消息，拼接并继续处理"""
        concatenated_message = " ".join(self.intercepted_messages[session_id])
        e_context["context"].content = concatenated_message
        self.intercepted_messages[session_id] = []  # 清空拦截的消息
        self.timers.pop(session_id, None)  # 移除计时器
        e_context.action = EventAction.CONTINUE  # 继续交给下个插件处理

    def get_help_text(self, **kwargs):
        help_text = "HumanLC插件会拦截私聊消息，并在拦截5次或超时10秒后将消息拼接在一起，然后继续处理。"
        return help_text
