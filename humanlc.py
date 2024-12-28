import plugins
from common.log import logger
from plugins import *
from bridge.context import ContextType

@plugins.register(name="humanlc", desc="A simple plugin that prints hello world", version="0.1", author="Your Name")
class humanlc(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[humanlc] inited")

    def on_handle_context(self, e_context: EventContext):
        logger.debug("[humanlc] Hello, world!")
        return
