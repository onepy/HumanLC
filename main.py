# encoding:utf-8
import asyncio
import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List

import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *


@plugins.register(
    name="HumanLikeChat",
    desire_priority=990,  # 高优先级，确保先处理
    hidden=True,
    desc="模拟人类对话行为，改善机器人回复的自然性",
    version="1.0",
    author="AI",
)
class HumanLikeChat(Plugin):
    def __init__(self):
        super().__init__()
        self.message_cache: List[Dict] = []
        self.private_message_cache: Dict[
            str, List[Dict]
        ] = {}  #  {session_id: messages}
        self.private_message_timers: Dict[str, asyncio.TimerHandle] = {}
        self.max_cache_size = 20
        self.max_message_age = 3600  # 1 hour
        self.private_message_max = 5
        self.private_message_delay = 10
        self.lock = threading.Lock()

        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[HumanLikeChat] inited")

    def _clear_old_messages(self):
        """清理过期的消息"""
        now = datetime.now()
        with self.lock:
            self.message_cache = [
                msg
                for msg in self.message_cache
                if now - msg["timestamp"] < timedelta(seconds=self.max_message_age)
            ]
    
    def _add_message_to_cache(self, sender, content, is_group, session_id=None):
        """将消息添加到缓存中"""
        now = datetime.now()
        message = {
            "sender": sender,
            "content": content,
            "timestamp": now,
            "is_group": is_group,
        }
        if session_id:
          message["session_id"]=session_id
        with self.lock:
            self.message_cache.append(message)
        
            if len(self.message_cache) > self.max_cache_size:
                self.message_cache.pop(0)  # 移除最旧的消息

    def _clear_private_message(self, session_id):
       with self.lock:
            if session_id in self.private_message_cache:
                del self.private_message_cache[session_id]
            if session_id in self.private_message_timers:
               self.private_message_timers[session_id].cancel()
               del self.private_message_timers[session_id]


    async def _send_private_message(self, session_id):
        """处理私聊消息，发送给GPT"""
        with self.lock:
            if session_id not in self.private_message_cache or not self.private_message_cache[session_id]:
                return
            messages = self.private_message_cache[session_id]
            self._clear_private_message(session_id)

        content = "
".join([f"{msg['sender']}: {msg['content']}" for msg in messages])
        logger.info(f"[HumanLikeChat] Send private messages to GPT, session_id:{session_id}, content:
 {content}")

        # 构建一个新的上下文
        context = messages[0].get('context')
        new_context = Context(ContextType.TEXT, content)
        new_context.kwargs = context.kwargs
        new_context["session_id"]=session_id
        e_context = PluginManager().emit_event(EventContext(Event.ON_HANDLE_CONTEXT, {"channel": context.kwargs.get("channel"), "context": new_context}))
        if e_context.is_pass():
           return

        reply = context.kwargs.get("channel")._generate_reply(new_context)
        if reply and reply.content:
            context.kwargs.get("channel")._send_reply(new_context, reply)

    def _reset_private_message_timer(self, session_id):
        """重置私聊消息的定时器"""
        with self.lock:
            if session_id in self.private_message_timers:
                self.private_message_timers[session_id].cancel()
            loop = asyncio.get_event_loop()
            timer = loop.call_later(
                self.private_message_delay,
                lambda: asyncio.create_task(self._send_private_message(session_id)),
            )
            self.private_message_timers[session_id] = timer
    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]
        if context.type not in [ContextType.TEXT, ContextType.VOICE]:
            return
        
        msg = context.get("msg")
        
        is_group = context.get("isgroup", False)
        sender = msg.actual_user_nickname if is_group else msg.from_user_nickname
        content = context.content
        session_id = context.get("session_id")
       
        self._add_message_to_cache(sender, content, is_group, session_id)
        self._clear_old_messages()
        logger.debug(f"[HumanLikeChat] Received message from {sender}, content: {content}, is_group: {is_group}, session_id:{session_id}")

        if is_group:
            # 群聊消息处理
            if not msg.is_at:
                e_context.action = EventAction.BREAK_PASS # 不发送给GPT，等待@
                return 
            else:
                e_context.action = EventAction.CONTINUE
                return  # 将消息发送给GPT处理
        else:
            # 私聊消息处理
            with self.lock:
                if session_id not in self.private_message_cache:
                    self.private_message_cache[session_id] = []
                
                self.private_message_cache[session_id].append(
                { "sender":sender,
                  "content":content,
                  "context": context,
                })

                if len(self.private_message_cache[session_id]) >= self.private_message_max:
                    asyncio.create_task(self._send_private_message(session_id))
                else:
                    self._reset_private_message_timer(session_id)
            e_context.action = EventAction.BREAK_PASS # 不直接发送，等待发送时机


    def get_help_text(self, **kwargs):
        return "模拟人类对话行为，改善机器人回复的自然性。
" \
               "  - 缓存最近20条消息，超过1小时的消息会被删除。
" \
               "  - 群聊消息只有在用户@bot时才会发送给GPT。
" \
               "  - 私聊消息会累积后延时发送，10秒内无新消息或累积5条消息时发送。"
