# encoding:utf-8

import time
import json
import random
import os
import re

import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *


@plugins.register(name="Robot2Human", desc="模拟人类发送消息", version="0.1", author="Your Name", desire_priority=50)
class Robot2Human(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.handlers[Event.ON_SEND_REPLY] = self.on_send_reply

        # 读取配置
        curdir = os.path.dirname(__file__)
        config_path = os.path.join(curdir, "config.json")

        if not os.path.exists(config_path):
            default_config = {
                "max_cached_records": 16,
                "max_cached_time": 600,  # 10分钟
                "tpc": 0.5,  # 打字时间系数
                "parse_flag": True,
                "max_len": 5,
                "truncate": 0.5,
                "bracket_prob": 0.3
            }
            with open(config_path, "w") as f:
                json.dump(default_config, f, indent=4)

        with open(config_path, 'r') as f:
            config = json.load(f)
            self.max_cached_records = config['max_cached_records']
            self.max_cached_time = config['max_cached_time']
            self.tpc = config["tpc"]
            self.parse_flag = config['parse_flag']
            self.max_len = config['max_len']
            self.truncate = config["truncate"]
            self.bracket_prob = config["bracket_prob"]

        self.chat_record = []
        logger.info("[Robot2Human] inited")

    def check_chat_record(self):
        self.chat_record = sorted(self.chat_record, key=lambda x: x[2])
        now = time.time()
        while self.chat_record and now - self.chat_record[0][2] > self.max_cached_time:
            del self.chat_record[0]
        while len(self.chat_record) > self.max_cached_records:
            del self.chat_record[0]

    def update_chat_record(self, user_id, text, timestamp):
        self.chat_record.append((user_id, text, timestamp))
        self.check_chat_record()

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type != ContextType.TEXT:
            return

        context = e_context['context']
        msg = context['msg']
        if msg:
            user_id = msg.from_user_id
            text = msg.content
            timestamp = msg.create_time
            self.update_chat_record(user_id, text, timestamp)

        e_context.action = EventAction.CONTINUE  # 交给下一个插件或默认逻辑处理


    def on_send_reply(self, e_context: EventContext):
        if e_context['reply'] and e_context['reply'].type == ReplyType.TEXT:
            original_reply = e_context['reply']  # 存储原始回复

            reply_content = original_reply.content
            if random.random() < self.bracket_prob:
                reply_content = f"{reply_content}（括号）"

            replies = self.split_reply(reply_content) # 分割后的回复

            context = e_context['context']
            for reply_text in replies:
                reply = Reply(ReplyType.TEXT, reply_text)  #  创建新的 Reply 对象
                e_context['channel'].send(context, reply)
                time.sleep(self.get_type_time(reply_text))

    def split_reply(self, text):
        if self.parse_flag:
            replies = re.split(r'[。？！；]', text)
            replies = [r.strip() for r in replies if r.strip()]
        else:
            replies = [text]

        if len(replies) > self.max_len and random.random() < self.truncate:  # 随机截断
            replies = replies[:self.max_len]
        return replies


    def get_type_time(self, string):
        return 1.5 + self.tpc * len(string)

