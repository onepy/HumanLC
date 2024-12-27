# encoding:utf-8

import time
import json
import os
from typing import List, Dict
import threading

import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *


@plugins.register(
    name="HumanLC",
    desire_priority=950,
    desc="模拟人类对话行为，改善机器人回复的自然性",
    version="1.0",
    author="AI",
)
class HumanLikeChat(Plugin):
    def __init__(self):
        super().__init__()
        self.message_cache: List[Dict] = []
        self.private_message_cache: Dict[str, List[Dict]] = {}
        self.private_message_timers: Dict[str, threading.Timer] = {}
        self.max_cache_size = 20
        self.max_message_age = 3600  # 1 hour
        self.private_message_max = 5
        self.private_message_delay = 10
        self.lock = threading.Lock()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[HumanLikeChat] inited")

    def _clear_expired_messages(self):
        now = time.time()
        self.message_cache = [
            msg
            for msg in self.message_cache
            if now - msg["timestamp"] <= self.max_message_age
        ]
        for session_id, messages in self.private_message_cache.items():
            self.private_message_cache[session_id] = [
                msg
                for msg in messages
                if now - msg["timestamp"] <= self.max_message_age
            ]
        

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]
        if context.type not in [ContextType.TEXT, ContextType.VOICE,ContextType.IMAGE]:
            return
        
        msg = context["msg"]
        session_id = context["session_id"]
        message_info = {
            "sender": msg.from_user_nickname,
            "content": context.content,
            "timestamp": time.time(),
            "is_group": context.get("isgroup", False),
            "actual_user_id": msg.actual_user_id,
            "is_at": msg.is_at,
        }

        with self.lock:
            self._clear_expired_messages()
            self.message_cache.append(message_info)
            if len(self.message_cache) > self.max_cache_size:
                self.message_cache.pop(0)

            if context.get("isgroup", False):
                # 群聊消息处理
                if msg.is_at:  # 只有当@bot时才处理群聊信息
                    self._handle_group_message(e_context, session_id)
                else:
                   
                    e_context.action = EventAction.BREAK_PASS
                return
            else:
                # 私聊消息处理
                self._handle_private_message(e_context, session_id, message_info)
        
        
    def _handle_group_message(self, e_context, session_id):
        context = e_context["context"]
        # 将所有缓存的群聊消息发送给 GPT
        with self.lock:
            group_messages = [
                msg["content"]
                for msg in self.message_cache
                if msg["is_group"] and msg["actual_user_id"] == context["msg"].actual_user_id
            ]
        
        if group_messages:
          
            combined_message = "
".join(group_messages)
            context.content = combined_message
            logger.debug(f"[HumanLC] Sending group messages to GPT: {combined_message}")
            e_context.action = EventAction.CONTINUE
            # 清空指定群聊的消息缓存
            self.message_cache = [
              msg for msg in self.message_cache if not (msg["is_group"] and msg["actual_user_id"] == context["msg"].actual_user_id)
            ]
        else:
            e_context.action = EventAction.BREAK_PASS
            logger.debug(f"[HumanLC] No group messages to send for {session_id}")

    def _handle_private_message(self, e_context, session_id, message_info):
        if session_id not in self.private_message_cache:
            self.private_message_cache[session_id] = []
        
        self.private_message_cache[session_id].append(message_info)
        
        if len(self.private_message_cache[session_id]) >= self.private_message_max:
                self._send_private_message(e_context, session_id)
                return
        
        if session_id in self.private_message_timers:
            self.private_message_timers[session_id].cancel()

        timer = threading.Timer(
            self.private_message_delay, self._send_private_message, args=[e_context, session_id]
        )
        self.private_message_timers[session_id] = timer
        timer.start()

        e_context.action = EventAction.BREAK_PASS
        logger.debug(f"[HumanLC] private message received, set timer for {session_id}")
    

    def _send_private_message(self, e_context, session_id):
         with self.lock:
            if session_id in self.private_message_timers:
                self.private_message_timers[session_id].cancel()
                del self.private_message_timers[session_id]

            if session_id not in self.private_message_cache or not self.private_message_cache[session_id]:
              
                return
            
            messages = self.private_message_cache[session_id]
            combined_message = "
".join([msg["content"] for msg in messages])
            e_context["context"].content = combined_message
            
            del self.private_message_cache[session_id]
            e_context.action = EventAction.CONTINUE
            logger.debug(f"[HumanLC] Sending private messages to GPT for {session_id}: {combined_message}")
    

    def get_help_text(self, **kwargs):
        return "模拟人类对话行为，改善机器人回复的自然性"
