import time
import threading
import plugins
from bridge.context import ContextType, Event, EventAction, EventContext
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from common.log import logger
from plugins import *
from config import conf
from common import memory
import os
import json

@plugins.register(
    name="HumanEmulator",
    desire_priority=800,
    hidden=True,
    desc="Emulates human-like conversation by caching messages.",
    version="0.2",
    author="onepy",
)
class HumanEmulator(Plugin):
    MAX_CACHE_SIZE = 20
    CACHE_EXPIRY_TIME = 3600
    PRIVATE_MSG_TIMEOUT = 10
    PRIVATE_MSG_THRESHOLD = 5
    
    def __init__(self):
        super().__init__()
        self.message_cache = {}
        self.private_sessions = {}
        try:
            self.config = super().load_config()
            if not self.config:
                self.config = self._load_config_template()
            self.MAX_CACHE_SIZE = self.config.get("max_cache_size", self.MAX_CACHE_SIZE)
            self.CACHE_EXPIRY_TIME = self.config.get("cache_expiry_time", self.CACHE_EXPIRY_TIME)
            self.PRIVATE_MSG_TIMEOUT = self.config.get("private_msg_timeout", self.PRIVATE_MSG_TIMEOUT)
            self.PRIVATE_MSG_THRESHOLD = self.config.get("private_msg_threshold", self.PRIVATE_MSG_THRESHOLD)
            logger.info("[HumanEmulator] inited")
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            self.handlers[Event.ON_GENERATE_REPLY] = self.on_generate_reply
            self._start_timer()
        except Exception as e:
            logger.error(f"[HumanEmulator]初始化异常：{e}")
            raise "[HumanEmulator] init failed, ignore "
    
    def _start_timer(self):
        self._timer = threading.Timer(self.PRIVATE_MSG_TIMEOUT, self._check_and_send_private_messages)
        self._timer.start()

    def _stop_timer(self):
        if self._timer and self._timer.is_alive():
            self._timer.cancel()
    
    def _check_and_send_private_messages(self):
        try:
            with threading.Lock():
                sessions_to_remove = []
                for session_id, session_data in self.private_sessions.items():
                    if not session_data["messages"]:
                        sessions_to_remove.append(session_id)
                        continue
                    
                    time_diff = time.time() - session_data["last_message_time"]
                    if time_diff >= self.PRIVATE_MSG_TIMEOUT or len(session_data["messages"]) >= self.PRIVATE_MSG_THRESHOLD:
                        messages = session_data["messages"]
                        self._send_messages_to_gpt(session_id, messages)
                        sessions_to_remove.append(session_id)
                for session_id in sessions_to_remove:
                   del self.private_sessions[session_id]

        except Exception as e:
            logger.error(f"[HumanEmulator] Error in _check_and_send_private_messages: {e}")
        finally:
            self._start_timer()


    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return

        msg:ChatMessage = e_context['context']['msg']
        session_id = e_context["context"]["session_id"]
        sender_id = msg.from_user_id  # 获取发送者ID
        message = e_context["context"].content  # 获取消息内容
        timestamp = time.time()  # 获取当前时间戳

        if e_context["context"].get("isgroup",False):
            if session_id not in self.message_cache:
               self.message_cache[session_id] = []
            self.message_cache[session_id].append((sender_id, message, timestamp))  # 添加到消息缓存
            self._clean_cache(session_id)

            while len(self.message_cache[session_id]) > self.MAX_CACHE_SIZE:
                self.message_cache[session_id].pop(0)
        else:
            # 处理私聊消息
            with threading.Lock():
              if session_id not in self.private_sessions:
                  self.private_sessions[session_id] = {
                      "messages": [],
                      "last_message_time": timestamp,
                  }
              self.private_sessions[session_id]["messages"].append((sender_id, message, timestamp))
              self.private_sessions[session_id]["last_message_time"] = timestamp
        e_context.action = EventAction.CONTINUE  # 继续事件传递
        logger.debug(f"[HumanEmulator] message cached, current cache size: {len(self.message_cache)}, private message: {len(self.private_sessions)}")

    def on_generate_reply(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return

        if e_context["context"].get("isgroup", False):
             session_id = e_context["context"]["session_id"]
             if session_id not in self.message_cache or not self.message_cache[session_id]:
                 return
             messages = self.message_cache[session_id]
             self._send_messages_to_gpt(session_id,messages,e_context)
             del self.message_cache[session_id] #清空缓存
             e_context.action = EventAction.BREAK_PASS
             
        else:
            e_context.action = EventAction.CONTINUE # 继续默认处理逻辑
        return
    
    def _send_messages_to_gpt(self, session_id, messages,e_context=None):
          all_messages = ""
          for sender, message, _ in messages:
              all_messages += f"{sender}: {message}
"
          if not all_messages:
            return
          if e_context:
            e_context["context"].content = all_messages
          else:
            memory.user_session(session_id).set(all_messages) # 如果没有上下文，放入内存
          logger.debug(f"[HumanEmulator] Sending messages to GPT: {all_messages}")

    def _clean_cache(self,session_id):
        if session_id not in self.message_cache:
            return
        current_time = time.time()
        self.message_cache[session_id] = [
            item for item in self.message_cache[session_id] if current_time - item[2] <= self.CACHE_EXPIRY_TIME
        ]

    def get_help_text(self, **kwargs):
        help_text = "这是一个模拟人类对话的插件，它会缓存最近的消息，以便后续进行更人性化的回复。
"
        help_text += f"当前最大缓存消息数: {self.MAX_CACHE_SIZE} 条。
"
        help_text += f"缓存消息过期时间: {self.CACHE_EXPIRY_TIME} 秒。
"
        help_text += f"私聊消息超时时间: {self.PRIVATE_MSG_TIMEOUT} 秒。
"
        help_text += f"私聊消息累积阈值: {self.PRIVATE_MSG_THRESHOLD} 条。
"
        return help_text
    def _load_config_template(self):
        logger.debug("No HumanEmulator plugin config.json, use plugins/humanemulator/config.json.template")
        try:
            plugin_config_path = os.path.join(self.path, "config.json.template")
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, "r", encoding="utf-8") as f:
                    plugin_conf = json.load(f)
                    return plugin_conf
        except Exception as e:
            logger.exception(e)

    def __del__(self):
        self._stop_timer()
