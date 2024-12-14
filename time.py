# encoding:utf-8

import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from common.log import logger
from plugins import *
from config import conf
import time
import requests
import os, json

@plugins.register(
    name="time",
    desire_priority=990,
    hidden=False,
    desc="A plugin that provides detailed time and optional IP information before sending messages to GPT.",
    version="1.0",
    author="onepy",
)
class Time(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[Time] inited")

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type not in [
            ContextType.TEXT,
            ContextType.SHARING,
            ContextType.FILE,
            ContextType.IMAGE,
            ContextType.VOICE,
        ]:
            return
        
        config = conf()
        # 获取当前详细时间
        current_time = self.get_detailed_time()

        # 使用.get()方法获取配置，如果键不存在则返回默认值False
        ip_info = ""
        if config.get("enable_ip_info", False):
            ip_info = self.get_ip_info()

        # 构建提示词
        prompt = f"Current time: {current_time}"
        if ip_info:
            prompt += f", Location: {ip_info}"
        prompt += ". "

        # 将提示词添加到消息内容前
        e_context["context"].content = prompt + e_context["context"].content

        logger.debug(f"[Time] Added time info: {prompt}")
        e_context.action = EventAction.CONTINUE


    def get_detailed_time(self):
        # 获取当前时间，精确到毫秒
        return time.strftime("%Y-%m-%d %H:%M:%S") + ".{:03d}".format(int(time.time() * 1000) % 1000)

    def get_ip_info(self):
        # 获取IP地址和地理位置信息
        try:
            response = requests.get("https://ipapi.co/json/")
            response.raise_for_status()  # 检查请求是否成功
            data = response.json()
            return f"{data.get('city', '')}, {data.get('country', '')} (IP: {data.get('ip', '')})"
        except requests.RequestException as e:
            logger.error(f"Error retrieving IP information: {e}")
            return "Unknown Location"
    
    def get_help_text(self, **kwargs):
        help_text = "此插件会在发送给GPT的消息前添加当前时间信息，根据配置可选地添加IP地址信息。"
        return help_text

    def _load_config_template(self):
        logger.debug("No Time plugin config.json, use plugins/time/config.json.template")
        try:
            plugin_config_path = os.path.join(self.path, "config.json.template")
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, "r", encoding="utf-8") as f:
                    plugin_conf = json.load(f)
                    return plugin_conf
        except Exception as e:
            logger.exception(e)
