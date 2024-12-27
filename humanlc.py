# encoding:utf-8

import json
import os
import threading
import time
from datetime import datetime, timedelta
from collections import deque

import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import *
from .lib.WordsSearch import WordsSearch


@plugins.register(
    name="humanlc",
    desire_priority=100,
    desc="判断消息中是否有敏感词、决定是否回复,并模拟人类对话",
    version="1.1",
    author="lanvent",
)
class humanlc(Plugin):
    def __init__(self):
        super().__init__()
        try:
            # load config
            conf = super().load_config()
            curdir = os.path.dirname(__file__)
            if not conf:
                # 配置不存在则写入默认配置
                config_path = os.path.join(curdir, "config.json")
                if not os.path.exists(config_path):
                    conf = {"action": "ignore"}
                    with open(config_path, "w") as f:
                        json.dump(conf, f, indent=4)

            self.searchr = WordsSearch()
            self.action = conf["action"]
            banwords_path = os.path.join(curdir, "banwords.txt")
            with open(banwords_path, "r", encoding="utf-8") as f:
                words = []
                for line in f:
                    word = line.strip()
                    if word:
                        words.append(word)
            self.searchr.SetKeywords(words)

            self.message_cache = deque(maxlen=20)  # 缓存最近20条消息
            self.private_message_cache = {}  # 缓存私聊消息，key是用户ID，value是消息列表
            self.private_message_timers = {} # 缓存私聊消息定时器，key是用户ID,value是定时器对象
            self.lock = threading.Lock()  # 用于线程安全的锁
            self.group_at_flag = False  # 群聊@标志，初始为False

            if conf.get("reply_filter", True):
                self.handlers[Event.ON_DECORATE_REPLY] = self.on_decorate_reply
                self.reply_action = conf.get("reply_action", "ignore")

            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            logger.info("[Banwords] inited")

        except Exception as e:
            logger.warn(
                "[Banwords] init failed, ignore or see https://github.com/zhayujie/chatgpt-on-wechat/tree/master/plugins/banwords ."
            )
            # 这里不应该直接 raise e ,避免插件加载失败
            # raise e

    def _is_message_expired(self, timestamp):
      """
      检查消息是否已过期 (超过1小时)
      """
      message_time = datetime.fromtimestamp(timestamp)
      return message_time < datetime.now() - timedelta(hours=1)


    def _clean_expired_messages(self):
       """
       清理过期的缓存消息
       """
       with self.lock:
          # 清理全局缓存
          while self.message_cache and self._is_message_expired(self.message_cache[0]["timestamp"]):
            self.message_cache.popleft()
          # 清理私聊缓存
          for user_id in list(self.private_message_cache):
            msgs = self.private_message_cache[user_id]
            while msgs and self._is_message_expired(msgs[0]["timestamp"]):
                msgs.pop(0)
            if not msgs:
                del self.private_message_cache[user_id]


    def _add_message_to_cache(self, user_id, content, isgroup, actual_user_nickname, actual_user_id):
        """
         将消息添加到缓存并清理过期消息
        """
        timestamp = time.time()
        message = {
            "user_id": user_id,
            "content": content,
            "timestamp": timestamp,
            "isgroup": isgroup,
            "actual_user_nickname": actual_user_nickname,
            "actual_user_id": actual_user_id,
        }

        with self.lock:
          self.message_cache.append(message)
          self._clean_expired_messages()


        # 分别缓存群聊和私聊
        if isgroup:
           logger.debug(f"[Banwords] Group message cache add: {message}")
           return
        else:
           logger.debug(f"[Banwords] Private message cache add: {message}")
           if user_id not in self.private_message_cache:
               self.private_message_cache[user_id] = []
           self.private_message_cache[user_id].append(message)


    def _send_private_messages(self, user_id, e_context):
         """
         发送私聊缓存消息
         """
         with self.lock:
            if user_id in self.private_message_cache:
              messages = self.private_message_cache[user_id]
              # 将所有缓存消息拼接
              combined_content = "
".join([msg["content"] for msg in messages])
              del self.private_message_cache[user_id]
              logger.debug(f"[Banwords] send private message to GPT: {combined_content}")
              # 将合并内容作为新的Context交给后续处理
              e_context["context"].content = combined_content
              e_context.action = EventAction.CONTINUE

    def _clear_private_message_timer(self, user_id):
       """
       取消定时器
       """
       if user_id in self.private_message_timers:
         timer = self.private_message_timers[user_id]
         timer.cancel()
         del self.private_message_timers[user_id]


    def _private_message_timer(self, user_id, e_context):
       """
       定时器函数，用于延时发送私聊消息
       """
       logger.debug(f"[Banwords] Private message timer timeout, user_id: {user_id}")
       self._send_private_messages(user_id, e_context)
       self._clear_private_message_timer(user_id)


    def _reset_private_message_timer(self, user_id, e_context):
      """
      重置私聊消息定时器
      """
      self._clear_private_message_timer(user_id)
      timer = threading.Timer(10, self._private_message_timer, args=[user_id, e_context])
      timer.start()
      self.private_message_timers[user_id] = timer
      logger.debug(f"[Banwords] Private message timer reset, user_id: {user_id}")

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type not in [
            ContextType.TEXT,
            ContextType.IMAGE_CREATE,
        ]:
            return

        content = e_context["context"].content
        logger.debug("[Banwords] on_handle_context. content: %s" % content)
        if self.action == "ignore":
            f = self.searchr.FindFirst(content)
            if f:
                logger.info("[Banwords] %s in message" % f["Keyword"])
                e_context.action = EventAction.BREAK_PASS
                return
        elif self.action == "replace":
            if self.searchr.ContainsAny(content):
                reply = Reply(ReplyType.INFO, "发言中包含敏感词，请重试: 
" + self.searchr.Replace(content))
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return

        context = e_context["context"]
        msg = context["msg"]
        isgroup = context.get("isgroup", False)
        user_id = msg.from_user_id
        actual_user_nickname = msg.actual_user_nickname
        actual_user_id = msg.actual_user_id
        self._add_message_to_cache(user_id, content, isgroup, actual_user_nickname, actual_user_id)


        if isgroup:
            if not msg.is_at: # 如果不是@消息，直接返回
                logger.debug("[Banwords] Group message not at, ignore.")
                e_context.action = EventAction.BREAK_PASS # 不处理非@消息
                return
            else: # 是@消息
               # 清空全局缓存，发送到gpt
               with self.lock:
                   combined_content = "
".join([msg["actual_user_nickname"]+":"+msg["content"] for msg in self.message_cache])
                   self.message_cache.clear() # 清空缓存
               logger.debug(f"[Banwords] group message at, send combined message to GPT: {combined_content}")
               e_context["context"].content = combined_content
               e_context.action = EventAction.CONTINUE
               return
        else:  # 私聊消息
           if user_id in self.private_message_cache:
             # 重置定时器
             self._reset_private_message_timer(user_id, e_context)
             # 检查消息是否超过5条
             if len(self.private_message_cache[user_id]) >= 5:
                self._send_private_messages(user_id, e_context)
                self._clear_private_message_timer(user_id)
             else:
                 e_context.action = EventAction.BREAK_PASS
           else:
             # 初始化消息列表和定时器
             self._reset_private_message_timer(user_id, e_context)
             e_context.action = EventAction.BREAK_PASS


    def on_decorate_reply(self, e_context: EventContext):
        if e_context["reply"].type not in [ReplyType.TEXT]:
            return

        reply = e_context["reply"]
        content = reply.content
        if self.reply_action == "ignore":
            f = self.searchr.FindFirst(content)
            if f:
                logger.info("[Banwords] %s in reply" % f["Keyword"])
                e_context["reply"] = None
                e_context.action = EventAction.BREAK_PASS
                return
        elif self.reply_action == "replace":
            if self.searchr.ContainsAny(content):
                reply = Reply(ReplyType.INFO, "已替换回复中的敏感词: 
" + self.searchr.Replace(content))
                e_context["reply"] = reply
                e_context.action = EventAction.CONTINUE
                return

    def get_help_text(self, **kwargs):
        return "过滤消息中的敏感词，并模拟人类对话行为。"
