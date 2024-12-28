# encoding: utf-8

import time
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *

@plugins.register(
    name="HumanLC",
    desire_priority=888,  # 设置较高的优先级，确保在其他插件之前拦截消息
    hidden=False,
    desc="A plugin that intercepts private chat messages and concatenates them before passing to the next step. Includes a timeout mechanism.",
    version="0.1",
    author="Pon",
)
class HumanLC(Plugin):
    def __init__(self):
        super().__init__()
        self.intercept_count = 5  # 拦截次数
        self.intercepted_messages = {}  # 用于存储拦截的消息
        self.last_message_time = {}  # 用于存储每个会话的最后一条消息的时间
        self.timeout = 10  # 超时时间，单位为秒
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[HumanLC] inited")

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]

        # 只拦截私聊消息
        if not context.get("isgroup", False):
            session_id = context["session_id"]
            content = context.content

            # 记录当前消息的时间
            current_time = time.time()

            # 如果会话首次收到消息，初始化时间和消息列表
            if session_id not in self.intercepted_messages:
                self.intercepted_messages[session_id] = []
                self.last_message_time[session_id] = current_time

            # 检查是否超时
            if self.is_timeout(session_id, current_time):
                logger.info(f"[HumanLC] Session {session_id} timed out. Processing intercepted messages.")
                self.process_intercepted_messages(session_id, e_context)
            else:
                self.intercepted_messages[session_id].append(content)

            # 检查是否达到拦截次数
            if len(self.intercepted_messages[session_id]) >= self.intercept_count:
                logger.info(f"[HumanLC] Session {session_id} reached intercept count. Processing intercepted messages.")
                self.process_intercepted_messages(session_id, e_context)
            else:
                e_context.action = EventAction.BREAK_PASS  # 拦截消息，不继续处理
        else:
            e_context.action = EventAction.CONTINUE  # 群聊消息正常处理

    def is_timeout(self, session_id, current_time):
        """检查是否超时"""
        if session_id in self.last_message_time:
            timeout_reached = current_time - self.last_message_time[session_id] >= self.timeout
            if timeout_reached:
                # 重置最后消息的时间为当前时间
                self.last_message_time[session_id] = current_time
            return timeout_reached
        return False

    def process_intercepted_messages(self, session_id, e_context):
        """处理拦截的消息，拼接并继续处理"""
        concatenated_message = " ".join(self.intercepted_messages[session_id])
        e_context["context"].content = concatenated_message
        self.intercepted_messages[session_id] = []  # 清空拦截的消息
        e_context.action = EventAction.CONTINUE  # 继续交给下个插件处理

    def get_help_text(self, **kwargs):
        help_text = "HumanLC插件会拦截私聊消息，并在拦截5次或超时10秒后将消息拼接在一起，然后继续处理。"
        return help_text
