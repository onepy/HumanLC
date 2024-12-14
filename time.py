# plugins/time/time.py
import datetime
from bridge.reply import Reply, ReplyType
from bridge.context import ContextType
import plugins
from plugins import Event, EventContext, EventAction

@plugins.register(
    name="Time",
    desc="A simple plugin that adds current time to the prompt",
    version="1.0",
    author="pon",
    desire_priority=990
)
class TimePlugin(plugins.Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[TimePlugin] initialized")

    def on_handle_context(self, e_context: EventContext):
        # 仅处理文本消息类型
        if e_context["context"].type != ContextType.TEXT:
            return

        # 获取当前时间，格式为 YYYY-MM-DD HH:MM:SS
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 获取原始内容
        original_content = e_context["context"].content
        
        # 创建新的提示信息
        prompt = f"The current time is {current_time}. User message: {original_content}"
        
        # 更新上下文内容
        e_context["context"].content = prompt
        logger.debug(f"[TimePlugin] modified prompt: {prompt}")
