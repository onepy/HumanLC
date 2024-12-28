import plugins
from common.log import logger
from plugins import *
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
import time
import threading

@plugins.register(name="humanlc", desc="A simple plugin that delays and accumulates private messages", version="0.2", author="Pon")
class humanlc(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.accumulated_messages = {}  # 用户 ID -> [消息列表, 最后消息时间]
        self.lock = threading.Lock()  # 用于线程安全的锁
        logger.info("[humanlc] inited")

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return  # 只处理文本消息
        
        msg = e_context["context"]["msg"]
        user_id = msg.from_user_id
        if e_context["context"].get("isgroup", False):
            return  # 跳过群聊消息
            
        with self.lock:
            if user_id not in self.accumulated_messages:
                self.accumulated_messages[user_id] = [[], None]
            
            message_list, last_message_time = self.accumulated_messages[user_id]
            message_list.append(e_context["context"].content)
            current_time = time.time()
            self.accumulated_messages[user_id][1] = current_time

        if len(message_list) < 5:
            time.sleep(10)  # 等待10秒
            with self.lock:
                if self.accumulated_messages[user_id][1] == current_time:
                    # 10秒内没有新消息
                    e_context["context"].content = " ".join(message_list)
                    self.accumulated_messages[user_id] = [[], None]  # 清空消息列表
                    logger.debug(f"[humanlc] userId:{user_id} accumulate_messages timeout, pass on to the next level. content: {e_context['context'].content}")
                    return  # 传递给下一个插件或默认逻辑
                else:
                    # 10秒内有新消息，拦截
                    e_context.action = EventAction.BREAK_PASS
                    logger.debug(f"[humanlc] userId:{user_id} accumulate_messages, count:{len(message_list)}, intercept message. content: {e_context['context'].content}")
                    return # 拦截消息
        else:
            # 累积够5条消息
            with self.lock:
                e_context["context"].content = " ".join(message_list)
                self.accumulated_messages[user_id] = [[], None]  # 清空消息列表
            logger.debug(f"[humanlc] userId:{user_id} accumulate_messages reach 5, pass on to the next level. content: {e_context['context'].content}")
            return # 传递给下一个插件或默认逻辑
