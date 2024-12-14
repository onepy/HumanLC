# plugins/time/time.py
import plugins
from plugins import *
from datetime import datetime
from bridge.context import ContextType

@plugins.register(name="Time", desc="Adds timestamp to prompt", version="1.0", author="Bard", desire_priority=990)
class TimePlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_DECORATE_REPLY] = self.add_timestamp

    def add_timestamp(self, e_context: EventContext):
        context = e_context["context"]
        reply = e_context["reply"]

        if reply and reply.type == ReplyType.TEXT and "prompt" in context: # Check if reply exists and is TEXT type.
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
                reply.content = f"{timestamp}: {reply.content}" #Add timestamp to the reply content directly.
            except Exception as e:
                logger.error(f"[TimePlugin] Error adding timestamp: {e}")
        e_context.action = EventAction.CONTINUE
