import plugins
from bridge.context import ContextType
from plugins import *
from datetime import datetime
from common.log import logger
import pytz

@plugins.register(name="Time", desc="Adds current time information to text messages.", version="0.1", author="Your Name", desire_priority=0)
class Time(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[Time] inited")

    def get_current_time_with_timezone(self,timezone_name):
        timezone = pytz.timezone(timezone_name)
        now = datetime.now(timezone)
        return now.strftime("%Y-%m-%d %H:%M:%S %Z%z")  # 格式化时区信息

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type != ContextType.TEXT:
            return

        # 获取当前时间，使用你的目标时区
        time_str = self.get_current_time_with_timezone("Asia/Shanghai")

        # 将时间信息添加到消息内容中
        original_content = e_context['context'].content
        modified_content = f"[Current Time: {time_str}] {original_content}"
        e_context['context'].content = modified_content

        logger.debug(f"[Time] Modified content to: {modified_content}")
        e_context.action = EventAction.CONTINUE

    def get_help_text(self, **kwargs):
         return "This plugin adds the current time (Asia/Shanghai) to the beginning of text messages."
