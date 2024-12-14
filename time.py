# encoding:utf-8
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *
import datetime


@plugins.register(
    name="Time",
    desc="Adds detailed time information to the beginning of each message before sending to GPT.",
    version="0.1",
    author="Pon",
    desire_priority=990,
)
class Time(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[Time] inited")

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type not in [ContextType.TEXT, ContextType.IMAGE_CREATE]:
            return  # 只处理文本和图片创建消息

        # 获取当前时间
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        prompt = f"Current Time: {timestamp}. Please analyze the following content:
" # 英文提示prompt
        
        # 添加时间信息和prompt到消息内容开头
        e_context['context'].content = prompt + e_context['context'].content
        
        e_context.action = EventAction.CONTINUE  # 继续交给下一个插件或默认逻辑处理

    def get_help_text(self, **kwargs):
        return "在消息开头添加时间信息。"

