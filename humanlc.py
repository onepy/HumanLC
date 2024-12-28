import plugins
from common.log import logger
from plugins import *
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
import threading
import time
from collections import deque

@plugins.register(name="humanlc", desc="A plugin that handles private messages with delay and accumulation", version="0.2", author="Your Name")
class humanlc(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.message_queues = {}  # Stores message queues for each user
        self.timers = {}  # Stores timers for each user
        self.lock = threading.Lock() #Lock for thread safe access
        self.delay_seconds = 10
        self.max_messages = 5
        logger.info("[humanlc] inited")

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type != ContextType.TEXT or e_context['context'].get("isgroup",False):
            return  # only process private text messages
        
        msg = e_context['context']['msg']
        user_id = msg.from_user_id
        content = e_context['context'].content
        
        with self.lock:
            if user_id not in self.message_queues:
                self.message_queues[user_id] = deque()
                self.timers[user_id] = None

            self.message_queues[user_id].append(e_context)
        
            if len(self.message_queues[user_id]) >= self.max_messages:
                 self._process_messages(user_id)
                 return

            if self.timers[user_id]:
                self.timers[user_id].cancel()
                
            self.timers[user_id] = threading.Timer(self.delay_seconds, self._process_messages, args=[user_id])
            self.timers[user_id].start()
        e_context.action = EventAction.BREAK_PASS #不让其他插件或者默认处理逻辑处理，等待累积到一起处理

    def _process_messages(self, user_id):
        with self.lock:
            if user_id not in self.message_queues or not self.message_queues[user_id]:
                return

            messages = list(self.message_queues[user_id])
            self.message_queues[user_id].clear()
            if self.timers[user_id]:
                self.timers[user_id].cancel()
                self.timers[user_id] = None


        combined_content = ""
        for e_context in messages:
             combined_content += e_context['context'].content+"
"
        
        combined_reply = Reply(ReplyType.TEXT, f"Combined messages:
{combined_content}")
        
        
        e_context_to_send = messages[0].copy()
        e_context_to_send['reply'] = combined_reply
        e_context_to_send.action = EventAction.CONTINUE #让后续的插件和默认逻辑处理
        PluginManager().emit_event(EventContext(Event.ON_DECORATE_REPLY, e_context_to_send))
        PluginManager().emit_event(EventContext(Event.ON_SEND_REPLY, e_context_to_send))
        
        logger.debug(f"[humanlc] Processed messages for user {user_id}")
