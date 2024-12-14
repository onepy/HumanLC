import plugins
from bridge.context import ContextType
from plugins import *
from datetime import datetime
from common.log import logger
import pytz

@plugins.register(name="Time", desc="告诉GPT当前时间, 并插入到system角色", version="0.1", author="pon", desire_priority=990)
class Time(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[Time] inited")

    def get_current_time_with_timezone(self, timezone_name):
        timezone = pytz.timezone(timezone_name)
        now = datetime.now(timezone)
        return now.strftime("%Y-%m-%d %H:%M:%S (%A)")

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type != ContextType.TEXT:
            return

        # 获取当前时间，使用你的目标时区
        time_str = self.get_current_time_with_timezone("Asia/Shanghai")

        # 插入到 system 角色的内容中
        system_message = f"当前时间是 {time_str}"

        # 假设 context['msg'] 是一个包含 role 和 content 的字典结构
        if 'msg' in e_context['context'] and isinstance(e_context['context']['msg'], dict):
            e_context['context']['msg'].setdefault('system', []).append({"role": "system", "content": system_message})

        logger.debug(f"[Time] Added system message: {system_message}")
        e_context.action = EventAction.CONTINUE

    def get_help_text(self, **kwargs):
        return "告诉GPT当前时间（上海时区），并将时间信息插入到system角色中"
