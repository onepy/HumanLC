import plugins
from bridge.context import ContextType
from plugins import *
from datetime import datetime
from common.log import logger
import pytz

@plugins.register(name="Time", desc="告诉gpt当前时间", version="0.1", author="pon", desire_priority=990)
class Time(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[Time] inited")

    def get_current_time_with_timezone(self,timezone_name):
        timezone = pytz.timezone(timezone_name)
        now = datetime.now(timezone)
        return now.strftime("%Y-%m-%d %H:%M:%S (%A)")

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type != ContextType.TEXT:
            return

        # 获取当前时间，使用你的目标时区
        time_str = self.get_current_time_with_timezone("Asia/Shanghai")

        # 将时间信息添加到消息内容中
        original_content = e_context['context'].content
        modified_content = f"{original_content} [{time_str}]"
        e_context['context'].content = modified_content

        logger.debug(f"[Time] Modified content to: {modified_content}")
        e_context.action = EventAction.CONTINUE

    def get_help_text(self, **kwargs):
         return "告诉GPT当前时间（上海时区）"
