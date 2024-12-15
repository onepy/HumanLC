import plugins
from bridge.context import ContextType
from plugins import *
from datetime import datetime
from common.log import logger
import pytz
import re

@plugins.register(name="Time", desc="告诉gpt当前时间", version="0.3", author="pon", desire_priority=990)
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

        content = e_context['context'].content.lower()  # 统一转为小写，方便匹配
        
        # 使用正则表达式匹配关键词
        time_keywords = [
            "现在时间", "当前时间", "几点", "日期", "今天几号", "什么时间", "时间是", 
            "请问现在几点", "现在是几点", "现在几时", "今天是几号", "今天是星期几",
            "现在日期", "当前日期", "当前时间日期", "现在的时间和日期", "现在是",
            "目前时间", "此刻时间", "查询时间", "告知时间", "报一下时间", "现在几点钟",
            "几点啦", "现在几点了", "时间几点了", "现在是几点钟", "今天多少号", "当前几点",
            "今天星期几","今天星期几呀","现在的时间","当前时刻","此刻的日期"
        ]
        if any(re.search(keyword, content) for keyword in time_keywords):
            # 获取当前时间，使用你的目标时区
            time_str = self.get_current_time_with_timezone("Asia/Shanghai")
            
            # 将时间信息添加到消息内容中
            original_content = e_context['context'].content
            modified_content = f"{original_content} [The current date and time is {time_str}]"
            e_context['context'].content = modified_content

            logger.debug(f"[Time] Modified content to: {modified_content}")
        
        e_context.action = EventAction.CONTINUE

    def get_help_text(self, **kwargs):
        return "告诉GPT当前时间（上海时区），你可以问我\"现在几点\"，\"当前时间\", \"日期\", \"今天几号\" 等"
