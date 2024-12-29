# encoding: utf-8

import time
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *

@plugins.register(
    name="HumanLC",
    desire_priority=800,
    hidden=False,
    desc="Intercepts and concatenates private messages after a timeout or count.",
    version="0.3",
    author="Pon",
)
class HumanLC(Plugin):

    def __init__(self):
        super().__init__()
        self.intercept_count = 5
        self.intercepted_messages = {}
        self.last_message_time = {}
        self.timeout = 10  # Seconds
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[HumanLC] Initialized")

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]
        if not context.get("isgroup", False):  # Only private messages
            session_id = context["session_id"]
            content = context.content
            current_time = time.time()

            if session_id not in self.intercepted_messages:
                self.intercepted_messages[session_id] = []
                
            if session_id in self.last_message_time:
                if self.is_timeout(session_id, current_time):
                    logger.info(f"[HumanLC] Timeout triggered for session {session_id}")
                    self.process_intercepted_messages(session_id, e_context)
                    return

            self.last_message_time[session_id] = current_time 
            self.intercepted_messages[session_id].append(content)

            if len(self.intercepted_messages[session_id]) >= self.intercept_count:
                logger.info(f"[HumanLC] Intercept count reached for session {session_id}")
                self.process_intercepted_messages(session_id, e_context)
            else:
                e_context.action = EventAction.BREAK_PASS  # Intercept, don't continue yet

        else:
            e_context.action = EventAction.CONTINUE # Group messages, continue processing


    def is_timeout(self, session_id, current_time):
        """Checks if timeout has occurred."""
        last_time = self.last_message_time.get(session_id)
        if last_time:
            return (current_time - last_time) >= self.timeout
        return False

    def process_intercepted_messages(self, session_id, e_context):
        """Processes intercepted messages, concatenates and continues."""
        concatenated_message = "
".join(self.intercepted_messages[session_id]) 

        if not concatenated_message.strip():
            logger.warning("[HumanLC] Concatenated message is empty, skipping processing.")
            self.intercepted_messages[session_id] = []
            self.last_message_time[session_id] = time.time()
            return

        e_context["context"].content = concatenated_message
        self.intercepted_messages[session_id] = []
        e_context.action = EventAction.CONTINUE

    def get_help_text(self, **kwargs):
        return "Intercepts and concatenates private messages after a timeout or count."

