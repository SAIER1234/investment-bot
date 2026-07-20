"""
Vercel Serverless — 微信投资助手
轻量版：收到消息 → DeepSeek → 客服消息回复
"""

import hashlib
import logging
import os
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import requests
from openai import OpenAI

logger = logging.getLogger("wechat")
logging.basicConfig(level=logging.INFO)

# 环境变量
AID = os.getenv("WECHAT_APPID", "")
ASEC = os.getenv("WECHAT_APPSECRET", "")
TOKEN = os.getenv("WECHAT_TOKEN", "investment_bot_token_2026")
DS_KEY = os.getenv("DEEPSEEK_API_KEY", "")

SYSTEM_PROMPT = """你是激进风格微信投资助手，服务一位学生（总资金~5万，生活压力小）。
用户实时持仓（参考）：
- 159516 半导体设备ETF国泰 计划买入20000元（尚未建仓）
- 003579 沪深300 已持有9500元
- 011613 科创50 已持有1400元
- 025766 港股通互联网 已持有12600元
- 018927 电池 已持有7300元

回复要求：先结论后理由，200-400字，干净排版，不确定就老实说。"""  # noqa: E501


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """微信服务器URL验证"""
        qs = parse_qs(urlparse(self.path).query)
        sig = qs.get("signature", [""])[0]
        ts = qs.get("timestamp", [""])[0]
        nonce = qs.get("nonce", [""])[0]
        echostr = qs.get("echostr", [""])[0]

        tmp = sorted([TOKEN, ts, nonce])
        sha1 = hashlib.sha1("".join(tmp).encode()).hexdigest()

        self._reply(200, echostr.encode() if sha1 == sig else b"fail")

    def do_POST(self):
        """接收消息 → 立即回success → 异步发客服消息"""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            msg = _parse_msg(body)
            if not msg:
                return self._reply(200, b"success")

            from_user = msg.get("FromUserName", "")
            user_msg = msg.get("Content", "").strip()
            logger.info(f"[{from_user}] {user_msg[:100]}")

            # 立即回复空串，微信不等
            self._reply(200, b"success")

            # 生成AI回复并推送
            reply = _chat(user_msg)
            if reply:
                _push(to=from_user, text=reply)

        except Exception as e:
            logger.error(f"ERR: {e}")
            self._reply(200, b"success")

    def _reply(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)


# ── AI 对话 ──────────────────────────────────────────────

def _chat(user_msg: str) -> str:
    if not user_msg:
        return "你好！试试问我持仓分析、基金建议、或者直接聊。"

    try:
        client = OpenAI(api_key=DS_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=800,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"DeepSeek: {e}")
        return ""


# ── 微信客服消息 ─────────────────────────────────────────

def _push(*, to: str, text: str):
    """通过客服消息API推送到用户微信"""
    try:
        token = _token()
        if not token:
            return
        url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={token}"
        r = requests.post(url, json={"touser": to, "msgtype": "text", "text": {"content": text}}, timeout=10)
        logger.info(f"push: {r.json()}")
    except Exception as e:
        logger.error(f"push fail: {e}")


def _token() -> str:
    try:
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={AID}&secret={ASEC}"
        r = requests.get(url, timeout=10)
        t = r.json().get("access_token", "")
        logger.info(f"token: {'OK' if t else r.json()}")
        return t
    except Exception as e:
        logger.error(f"token fail: {e}")
        return ""


# ── XML ──────────────────────────────────────────────────

def _parse_msg(xml: bytes) -> dict | None:
    try:
        return {c.tag: c.text for c in ET.fromstring(xml)}
    except ET.ParseError:
        return None
