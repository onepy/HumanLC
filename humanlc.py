# encoding: utf-8

import time
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *
import json
import os

@plugins.register(
    name="HumanLC",
    desire_priority=800,
    hidden=False,
    desc="Intercepts and concatenates private messages after a timeout or count.",
    version="0.3",
    author="Pon",
)
class HumanLC(Plugin):
    # 默认配置
    MAX_LENGTH = 8192  # 最大消息长度
    CLEAN_INTERVAL = 300  # 清理间隔(秒)

    def __init__(self):
        super().__init__()
        try:
            # 加载配置
            self.config = super().load_config()
            if not self.config:
                self.config = self._load_config_template()
            
            self.intercept_count = self.config.get('intercept_count', 5)
            self.timeout = self.config.get('timeout', 10)
            self.max_length = self.config.get('max_length', self.MAX_LENGTH)
            
            # 初始化数据结构
            self.intercepted_messages = {}
            self.last_message_time = {}
            self.last_clean_time = time.time()
            
            # 注册事件处理器
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            logger.info(f"[HumanLC] Initialized with: intercept_count={self.intercept_count}, timeout={self.timeout}s")
        except Exception as e:
            logger.error(f"[HumanLC] Initialize failed: {e}")
            raise e

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]
        
        # 只处理私聊消息
        if not context.get("isgroup", False):
            session_id = context["session_id"]
            content = context.content
            current_time = time.time()

            # 定期清理过期会话
            if current_time - self.last_clean_time > self.CLEAN_INTERVAL:
                self.clean_expired_sessions()
                self.last_clean_time = current_time

            # 初始化新会话
            if session_id not in self.intercepted_messages:
                self.intercepted_messages[session_id] = []
                self.last_message_time[session_id] = current_time

            # 检查超时
            if self.is_timeout(session_id, current_time):
                logger.debug(f"[HumanLC] Timeout triggered for session {session_id}")
                if self.intercepted_messages[session_id]:  # 只在有消息时处理
                    self.process_intercepted_messages(session_id, e_context)
                # 重置后继续处理新消息
                self.intercepted_messages[session_id] = [content]
                self.last_message_time[session_id] = current_time
                return

            # 追加新消息
            self.intercepted_messages[session_id].append(content)
            self.last_message_time[session_id] = current_time

            # 检查消息数量
            if len(self.intercepted_messages[session_id]) >= self.intercept_count:
                logger.debug(f"[HumanLC] Intercept count reached for session {session_id}")
                self.process_intercepted_messages(session_id, e_context)
            else:
                e_context.action = EventAction.BREAK_PASS  # 继续拦截

        else:
            e_context.action = EventAction.CONTINUE  # 群消息直接继续处理

    def is_timeout(self, session_id, current_time):
        """检查是否超时"""
        last_time = self.last_message_time.get(session_id)
        if last_time:
            return (current_time - last_time) >= self.timeout
        return False

    def process_intercepted_messages(self, session_id, e_context):
        """处理已拦截的消息"""
        try:
            concatenated_message = " ".join(self.intercepted_messages[session_id])
            
            # 检查消息是否为空
            if not concatenated_message.strip():
                logger.warning("[HumanLC] Concatenated message is empty, skipping processing.")
                self.reset_session(session_id)
                return

            # 限制消息长度
            if len(concatenated_message) > self.max_length:
                logger.warning(f"[HumanLC] Message too long ({len(concatenated_message)}), truncating to {self.max_length}")
                concatenated_message = concatenated_message[:self.max_length]

            # 更新context内容
            e_context["context"].content = concatenated_message
            e_context.action = EventAction.CONTINUE

            # 重置会话数据
            self.reset_session(session_id)
            
            logger.debug(f"[HumanLC] Processed messages for session {session_id}: {concatenated_message}")
        except Exception as e:
            logger.error(f"[HumanLC] Error processing messages: {e}")
            self.reset_session(session_id)

    def reset_session(self, session_id):
        """重置会话数据"""
        self.intercepted_messages[session_id] = []
        self.last_message_time[session_id] = time.time()

    def clean_expired_sessions(self):
        """清理过期会话"""
        try:
            current_time = time.time()
            expired_sessions = []
            
            for session_id in self.last_message_time:
                if current_time - self.last_message_time[session_id] > self.timeout * 2:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.intercepted_messages[session_id]
                del self.last_message_time[session_id]
                
            if expired_sessions:
                logger.debug(f"[HumanLC] Cleaned {len(expired_sessions)} expired sessions")
        except Exception as e:
            logger.error(f"[HumanLC] Error cleaning expired sessions: {e}")

    def get_help_text(self, **kwargs):
        help_text = f"连续发送消息时，将在以下条件自动合并:\n"
        help_text += f"1. 消息数量达到 {self.intercept_count} 条\n"
        help_text += f"2. 两条消息间隔超过 {self.timeout} 秒\n"
        help_text += f"最大消息长度限制为 {self.max_length} 字符"
        return help_text

    def _load_config_template(self):
        """加载配置模板"""
        try:
            plugin_config_path = os.path.join(self.path, "config.json.template")
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {
                "intercept_count": 5,
                "timeout": 10,
                "max_length": self.MAX_LENGTH
            }
        except Exception as e:
            logger.error(f"[HumanLC] Error loading config template: {e}")
            raise e
