# encoding:utf-8
import json
import os
import threading
import time
from typing import List

import plugins
from bridge.context import ContextType, Context
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import Event, EventAction, EventContext, Plugin
from plugins import *


@plugins.register(
    name="HumanEmulator",
    desire_priority=800,
    hidden=False,
    desc="模拟人类对话行为的插件",
    version="1.0",
    author="chatgpt",
)
class HumanEmulator(Plugin):
    def __init__(self):
        super().__init__()
        self.message_cache = {}  # 群聊消息缓存，key为session_id, value为 (sender, message, timestamp) 的列表
        self.private_sessions = {}  # 私聊消息缓存, key为session_id, value为 { "messages": [ (sender, message, timestamp) ], "last_message_time": timestamp }
        self.lock = threading.Lock()
        self.MAX_CACHE_SIZE = 20
        self.CACHE_EXPIRY_TIME = 3600  # 1 hour
        self.PRIVATE_MSG_TIMEOUT = 10  # seconds
        self.PRIVATE_MSG_THRESHOLD = 5
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.config_template_path = os.path.join(os.path.dirname(__file__), "config.json.template")

        # 加载配置
        self._load_config()

        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.handlers[Event.ON_GENERATE_REPLY] = self.on_generate_reply

        self.timer = threading.Timer(self.PRIVATE_MSG_TIMEOUT, self._check_and_send_private_messages)
        self.timer.start()

        logger.info("[HumanEmulator] inited")

    def _load_config(self):
        """加载配置文件"""
        if not os.path.exists(self.config_path):
            if os.path.exists(self.config_template_path):
                logger.info(f"[HumanEmulator] config.json not found, copy config.json.template to config.json")
                with open(self.config_template_path, 'r') as f:
                    config = json.load(f)
                with open(self.config_path, 'w') as f:
                    json.dump(config, f, indent=4)
            else:
                logger.warn(f"[HumanEmulator] config.json not found, using default config")
                return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.MAX_CACHE_SIZE = config.get("MAX_CACHE_SIZE", 20)
                self.CACHE_EXPIRY_TIME = config.get("CACHE_EXPIRY_TIME", 3600)
                self.PRIVATE_MSG_TIMEOUT = config.get("PRIVATE_MSG_TIMEOUT", 10)
                self.PRIVATE_MSG_THRESHOLD = config.get("PRIVATE_MSG_THRESHOLD", 5)
                logger.info(f"[HumanEmulator] Loaded config: {config}")
        except Exception as e:
            logger.error(f"[HumanEmulator] Failed to load config: {e}, using default config")

    def on_handle_context(self, e_context: EventContext):
        """处理消息，缓存消息或发送消息"""
        if e_context["context"].type != ContextType.TEXT:
            return
        
        context = e_context["context"]
        message = context.content
        sender = context["msg"].from_user_id
        timestamp = time.time()
        session_id = context["session_id"]
        isgroup = context.get("isgroup", False)


        if isgroup:  # 群聊消息
            with self.lock:
                if session_id not in self.message_cache:
                    self.message_cache[session_id] = []
                self.message_cache[session_id].append((sender, message, timestamp))
                self._clean_cache(session_id) # 清理过期消息和限制缓存大小
        else:  # 私聊消息
            with self.lock:
                if session_id not in self.private_sessions:
                    self.private_sessions[session_id] = {
                        "messages": [],
                        "last_message_time": timestamp
                    }
                self.private_sessions[session_id]["messages"].append((sender, message, timestamp))
                self.private_sessions[session_id]["last_message_time"] = timestamp
        e_context.action = EventAction.CONTINUE  # 继续传递事件

    def on_generate_reply(self, e_context: EventContext):
        """
        检查是否需要发送消息给GPT，群聊@，私聊超时或消息数量达到阈值
        """
        context = e_context["context"]
        session_id = context["session_id"]
        isgroup = context.get("isgroup", False)
        if isgroup:
            if context["msg"].is_at:
                with self.lock:
                    if session_id in self.message_cache:
                        messages = self.message_cache[session_id]
                        self._send_messages_to_gpt(context, messages)
                        self.message_cache[session_id] = []
                        e_context.action = EventAction.BREAK_PASS
                        return
        e_context.action = EventAction.CONTINUE

    def _check_and_send_private_messages(self):
        """定时检查私聊消息是否超时或达到阈值"""
        with self.lock:
            sessions_to_remove = []
            for session_id, session_data in self.private_sessions.items():
                if not session_data["messages"]:
                   sessions_to_remove.append(session_id)
                   continue
                
                last_message_time = session_data["last_message_time"]
                messages = session_data["messages"]
                if (time.time() - last_message_time >= self.PRIVATE_MSG_TIMEOUT or len(messages) >= self.PRIVATE_MSG_THRESHOLD) :
                    self._send_messages_to_gpt(Context(), messages, session_id)
                    sessions_to_remove.append(session_id)
            for session_id in sessions_to_remove:
                del self.private_sessions[session_id]

        self.timer = threading.Timer(self.PRIVATE_MSG_TIMEOUT, self._check_and_send_private_messages)
        self.timer.start()

    def _send_messages_to_gpt(self, context:Context, messages: List, session_id=None):
        """将消息列表发送给GPT"""
        if not messages:
            return
        
        formatted_messages = []
        for sender, message, _ in messages:
           formatted_messages.append(f"{sender}: {message}")
        content = "
".join(formatted_messages)
        if session_id: # 私聊
            memory_key = "human_emulator_private_" + session_id
        else: # 群聊
            memory_key = "human_emulator_group_" + context["session_id"]
        if memory_key:
            memory_content = f"以下是用户消息:
{content}"
            from common import memory
            memory.set_memory(memory_key,memory_content)
            context["memory_key"] = memory_key
            logger.debug(f"[HumanEmulator] send message to gpt. key:{memory_key}, content:{memory_content}")


    def _clean_cache(self, session_id):
        """清理缓存中的过期消息和限制缓存大小"""
        now = time.time()
        self.message_cache[session_id] = [
            (sender, message, ts)
            for sender, message, ts in self.message_cache[session_id]
            if now - ts <= self.CACHE_EXPIRY_TIME
        ]
        if len(self.message_cache[session_id]) > self.MAX_CACHE_SIZE:
             self.message_cache[session_id] = self.message_cache[session_id][-self.MAX_CACHE_SIZE:]


    def get_help_text(self, **kwargs):
        help_text = """
        HumanEmulator Plugin:
        模拟人类的对话行为，具有以下功能：
        - 群聊消息缓存：缓存群聊消息，等待用户 @ 机器人时发送给 GPT。
        - 私聊消息延时：私聊消息不立即发送给 GPT，而是等待超时或消息数量达到阈值。
        - 可配置参数：
            - MAX_CACHE_SIZE：最大缓存消息数量，默认为 20。
            - CACHE_EXPIRY_TIME：消息缓存时间，单位秒，默认为 3600 （1小时）。
            - PRIVATE_MSG_TIMEOUT：私聊消息超时时间，单位秒，默认为 10。
            - PRIVATE_MSG_THRESHOLD：私聊消息累积阈值，默认为 5。
        配置信息在 plugins/humanemulator/config.json 文件中。
        """
        return help_text
