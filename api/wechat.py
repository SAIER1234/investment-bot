"""
Vercel Serverless — 微信投资助手
直接回复模式：WeChat POST → DeepSeek → XML回复（无需客服消息API）
"""

import hashlib
import logging
import os
import time
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from openai import OpenAI

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wechat")

TOKEN = os.getenv("WECHAT_TOKEN", "investment_bot_token_2026")
DS_KEY = os.getenv("DEEPSEEK_API_KEY", "")

SP = """你是激进风格微信投资助手，服务一位学生（总资金~5万，生活压力小）。
用户实时持仓：
- 159516 半导体设备ETF国泰 计划买入20000元（尚未建仓）
- 003579 沪深300 持有9500元
- 011613 科创50 持有1400元
- 025766 港股通互联网 持有12600元
- 018927 电池 持有7300元
回复：先结论后理由，200-400字，干净排版，不确定就说。"""  # noqa: E501


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        sig = q.get("signature", [""])[0]
        ts = q.get("timestamp", [""])[0]
        nonce = q.get("nonce", [""])[0]
        echo = q.get("echostr", [""])[0]
        sha = hashlib.sha1("".join(sorted([TOKEN, ts, nonce])).encode()).hexdigest()
        body = echo.encode() if sha == sig else b"fail"
        self._ok(body)

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            xml = self.rfile.read(n)
            msg = {c.tag: c.text for c in ET.fromstring(xml)}
            user = msg.get("Content", "").strip()
            frm = msg.get("FromUserName", "")
            to = msg.get("ToUserName", "")
            log.info(f"[{frm}] {user[:100]}")

            reply = _ai(user)
            self._ok(_xml(to=frm, frm=to, text=reply).encode())

        except Exception as e:
            log.error(f"ERR: {e}")
            self._ok(b"success")

    def _ok(self, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)


def _ai(msg: str) -> str:
    if not msg:
        return "你好！试试问我持仓分析、基金建议、或者直接聊。"
    try:
        from openai import OpenAI
        c = OpenAI(api_key=DS_KEY, base_url="https://api.deepseek.com")
        r = c.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": SP}, {"role": "user", "content": msg}],
            temperature=0.7, max_tokens=800,
        )
        return r.choices[0].message.content or "我没想好，换个问法？"
    except Exception as e:
        log.error(f"AI: {e}")
        return "AI暂时不可用，稍后再试。"


def _xml(to: str, frm: str, text: str) -> str:
    t = int(time.time())
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to}]]></ToUserName>"
        f"<FromUserName><![CDATA[{frm}]]></FromUserName>"
        f"<CreateTime>{t}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{text}]]></Content>"
        "</xml>"
    )
