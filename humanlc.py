# encoding: utf-8

import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *

@plugins.register(
    name="HumanLC",
    desire_priority=500,  # 设置较高的优先级，确保在其他插件之前拦截消息
    hidden=False,
    desc="A plugin that intercepts private chat messages and concatenates them before passing to the next step.",
    version="0.1",
    author="YourName",
)
class HumanLC(Plugin):
    def __init__(self):
        super().__init__()
        self.intercept_count = 5  # 拦截次数
        self.intercepted_messages = {}  # 用于存储拦截的消息
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[HumanLC] inited")

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]

        # 只拦截私聊消息
        if not context.get("isgroup", False):
            session_id = context["session_id"]
            content = context.content

            if session_id not in self.intercepted_messages:
                self.intercepted_messages[session_id] = []

            self.intercepted_messages[session_id].append(content)

            # 拦截次数达到5次时，拼接消息并继续处理
            if len(self.intercepted_messages[session_id]) >= self.intercept_count:
                concatenated_message = " ".join(self.intercepted_messages[session_id])
                context.content = concatenated_message
                self.intercepted_messages[session_id] = []  # 清空拦截的消息
                e_context.action = EventAction.CONTINUE  # 继续交给下个插件处理
            else:
                e_context.action = EventAction.BREAK_PASS  # 拦截消息，不继续处理
        else:
            e_context.action = EventAction.CONTINUE  # 群聊消息正常处理

    def get_help_text(self, **kwargs):
        help_text = "HumanLC插件会拦截私聊消息，并在拦截5次后将消息拼接在一起，然后继续处理。"
        return help_text
