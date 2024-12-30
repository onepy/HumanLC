# encoding:utf-8
import re
import time
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *

@plugins.register(
    name="SplitReply",
    desc="将机器人生成的回复拆分为多个小句子并延迟发送。",
    version="1.1",
    author="Pon",
    desire_priority=500  # 优先级设置为 0，可根据需求调整
)
class SplitReply(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_SEND_REPLY] = self.on_send_reply
        logger.info("[SplitReply] inited")

    def on_send_reply(self, e_context: EventContext):
        reply = e_context['reply']
        context = e_context['context']

        if reply.type == ReplyType.TEXT:
            # 将回复文本按中文逗号和英文逗号拆分为句子
            sentences = re.split(r'[，,]', reply.content)
            sentences = [s.strip() for s in sentences if s.strip()]

            # 如果只有一个句子且长度小于等于 3 个字符，直接发送
            if len(sentences) == 1 and len(sentences[0]) <= 3:
                return

            # 过滤掉少于 3 个字符的句子
            sentences = [s for s in sentences if len(s) >= 3]

            # 如果没有有效的句子，直接返回
            if not sentences:
                return

            # 按每个字符延迟 0.4 秒发送每个句子
            for sentence in sentences:
                time.sleep(0.4 * len(sentence))
                context['channel'].send(sentence, context)

            # 标记事件已处理
            e_context.action = EventAction.BREAK_PASS
        else:
            # 对于非文本回复，延迟 2 秒后发送
            time.sleep(2)
            context['channel'].send(reply, context)
            e_context.action = EventAction.BREAK_PASS
