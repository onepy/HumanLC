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
        self.accumulated_messages = {}  # 用户 ID -> [消息列表, 最后消息时间, threading.Event()]
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
                event = threading.Event()
                self.accumulated_messages[user_id] = [[], None, event]
            message_list, last_message_time, event = self.accumulated_messages[user_id]
            message_list.append(e_context["context"].content)
            current_time = time.time()
            self.accumulated_messages[user_id][1] = current_time

        if len(message_list) < 5:
            if not event.is_set():  # 如果没有设置超时
                threading.Thread(target=self.wait_timeout, args=(user_id, current_time, e_context), daemon=True).start()  # 创建新的线程进行超时等待
                logger.debug(f"[humanlc] userId:{user_id} accumulate_messages, count:{len(message_list)}, intercept message. content: {e_context['context'].content}")
                e_context.action = EventAction.BREAK_PASS # 拦截消息，不传递给后续流程
                return
            else:
                # 超时线程处理过了，消息传递给下一个流程
                with self.lock:
                    if user_id in self.accumulated_messages:
                      self.accumulated_messages[user_id][2].clear() # 清除超时标记
                return
        else:
            # 累积够5条消息
            with self.lock:
                e_context["context"].content = " ".join(message_list)
                self.accumulated_messages[user_id] = [[], None, threading.Event()]  # 清空消息列表
            logger.debug(f"[humanlc] userId:{user_id} accumulate_messages reach 5, pass on to the next level. content: {e_context['context'].content}")
            return  # 默认传递给下一个流程


    def wait_timeout(self, user_id, current_time, e_context):
        event = self.accumulated_messages[user_id][2]
        if event.wait(10): # 设置超时时间
            return # 被其他消息线程设置超时了
        
        with self.lock:
            if user_id not in self.accumulated_messages:
                return
            message_list, last_message_time, _ = self.accumulated_messages[user_id]
            if last_message_time == current_time and len(message_list) > 0: # 10秒内没有收到新消息,并且有消息需要处理
                e_context["context"].content = " ".join(message_list)
                self.accumulated_messages[user_id] = [[], None, threading.Event()] # 清空消息列表
                logger.debug(f"[humanlc] userId:{user_id} accumulate_messages timeout, pass on to the next level. content: {e_context['context'].content}")
                event.set()
            
