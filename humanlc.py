import threading
import time
from typing import List

from core import plugins
from core.event import Event, EventContext, EventAction
from core.context import ContextType, Context
from core.reply import Reply

@plugins.register(name="AccumulateMessage", desc="Accumulate user messages and send them after 5 messages or timeout.", version="1.0", author="CAN")
class AccumulateMessage:
    def __init__(self):
        self.accumulated_messages = {}
        Event.ON_HANDLE_CONTEXT.register(self.on_handle_context)
        self.lock = threading.Lock()


    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return

        msg = e_context["context"].content
        user_id = e_context["context"].user_id

        if e_context["context"].is_group:
            return

        with self.lock:
            if user_id not in self.accumulated_messages:
                self.accumulated_messages[user_id] = [[], None, None]
            
            message_list, last_message_time, event = self.accumulated_messages[user_id]
            current_time = time.time()
            message_list.append(msg)
            self.accumulated_messages[user_id][1] = current_time
            
            if event is None:
                event = threading.Event()
                self.accumulated_messages[user_id][2] = event
                threading.Thread(target=self.wait_timeout, args=(user_id,), daemon=True).start()
           
            if len(message_list) < 5:
                e_context.action = EventAction.CONTINUE
                return
            else:
                combined_message = "
".join(message_list)
                self.accumulated_messages[user_id][0] = []  # clear message_list
                
                # Create Reply object
                reply = Reply()
                reply.content = combined_message
                e_context['reply'] = reply
                e_context.action = EventAction.BREAK_PASS
                self.accumulated_messages[user_id][2].set() #Set event to stop timeout
                self.accumulated_messages[user_id][2] = None
                return

    def wait_timeout(self, user_id):
        with self.lock:
            message_list, last_message_time, event = self.accumulated_messages[user_id]
        if event is None:
            return
        event.wait(10)

        with self.lock:
            message_list, last_message_time, event = self.accumulated_messages[user_id]
            current_time = time.time()

            if event is None or not message_list or (last_message_time != current_time):
                return

            combined_message = "
".join(message_list)
            self.accumulated_messages[user_id][0] = []  # clear message_list
            
            reply = Reply()
            reply.content = combined_message
            e_context = EventContext(context=Context(type=ContextType.TEXT, content=combined_message, user_id=user_id))
            e_context['reply'] = reply
            e_context.action = EventAction.BREAK_PASS
            self.accumulated_messages[user_id][2] = None
            Event.ON_HANDLE_CONTEXT.call(e_context)

