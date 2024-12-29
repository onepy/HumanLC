# encoding:utf-8

import plugins
import time
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from common.log import logger
from plugins import *

@plugins.register(
    name="humanlc",
    desire_priority=55,  # 默认优先级为0, 您可根据需要进行调整
    hidden=False,
    desc="Simulates human chat behavior, delays replies and sends in segments.",
    version="0.1",
    author="CAN",
)
class humanlc(Plugin):

    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.handlers[Event.ON_SEND_REPLY] = self.on_send_reply
        self.cached_messages = {}  # 存储每个session的缓存消息
        self.last_message_time = {} # 存储每个session的最后一条消息的时间戳

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT or e_context["context"].get("isgroup", False):  # 只处理私聊文本消息
            return

        session_id = e_context["context"]["session_id"]
        current_time = time.time()
        content = e_context["context"].content

        if session_id not in self.cached_messages:
            self.cached_messages[session_id] = []
            self.last_message_time[session_id] = current_time

        if len(self.cached_messages[session_id]) >= 5 or current_time - self.last_message_time[session_id] > 10:
            combined_content = "
".join(self.cached_messages[session_id] + [content])  # 拼接消息
            e_context["context"].content = combined_content
            self.cached_messages[session_id] = [] #清除缓存消息
            self.last_message_time[session_id] = current_time  # 更新时间戳
            e_context.action = EventAction.CONTINUE # 交给默认逻辑或下一个插件处理
        else:
            self.cached_messages[session_id].append(content)  # 添加到缓存
            self.last_message_time[session_id] = current_time  # 更新时间戳
            e_context.action = EventAction.BREAK_PASS # 拦截消息


    def on_send_reply(self, e_context: EventContext):
        reply = e_context["reply"]
        if not reply or reply.type != ReplyType.TEXT:
            return

        segments = reply.content.split(",")  # 按照逗号分段
        for segment in segments:
            e_context["channel"].send(Reply(ReplyType.TEXT, segment.strip()), e_context["context"]) # 发送分段回复
            typing_delay = len(segment.strip()) * 0.1  # 模拟打字延迟，可根据需要调整
            time.sleep(typing_delay)


    def get_help_text(self, **kwargs):
        return "这个插件模拟人类聊天，会延时回复并分段发送消息。"


