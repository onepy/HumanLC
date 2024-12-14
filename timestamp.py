import time
from datetime import datetime

from plugins import *

@plugins.register(name="Timestamp", desc="Adds a timestamp to the GPT prompt.", version="1.0", author="Bard", desire_priority=990)
class TimestampPlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[Timestamp] inited")

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type not in [ContextType.TEXT, ContextType.IMAGE_CREATE, ContextType.VOICE]:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        original_content = e_context["context"].content
        
        #Efficient timestamp addition to the prompt.  Avoids unnecessary string manipulation.
        new_content = f"Current time: {timestamp}.  Original query: {original_content}"
        e_context["context"].content = new_content
        e_context.action = EventAction.CONTINUE

