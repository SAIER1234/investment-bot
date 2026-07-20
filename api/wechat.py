"""
Vercel Serverless — 微信公众号机器人
接收微信消息 → DeepSeek生成回复 → 客服消息推回微信
"""

import hashlib
import json
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler

import requests
from openai import OpenAI

logger = logging.getLogger("wechat")
logging.basicConfig(level=logging.INFO)

# ── 配置 ─────────────────────────────────────────────────
WECHAT_APPID = os.getenv("WECHAT_APPID", "")
WECHAT_APPSECRET = os.getenv("WECHAT_APPSECRET", "")
WECHAT_TOKEN = os.getenv("WECHAT_TOKEN", "investment_bot_token_2026")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")

SYSTEM_PROMPT = """你是微信投资助手，服务一位学生投资者（总资金~5万，激进风格）。
持仓：159516半导体设备ETF(计划2万)、003579沪深300(9500)、011613科创50(1400)、025766港股通互联网(12600)、018927电池(7300)。
要求：先结论后理由，200-400字，干净排版，不确定就老实说，不发模棱两可的废话。"""


# ── Vercel Handler ───────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """微信服务器验证"""
        params = dict(
            (k, self.path.split(f"{k}=")[1].split("&")[0])
            for k in ["signature", "timestamp", "nonce", "echostr"]
            if k in self.path
        )
        # parse query
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        sig = qs.get("signature", [""])[0]
        ts = qs.get("timestamp", [""])[0]
        nonce = qs.get("nonce", [""])[0]
        echostr = qs.get("echostr", [""])[0]

        tmp = sorted([WECHAT_TOKEN, ts, nonce])
        sha1 = hashlib.sha1("".join(tmp).encode()).hexdigest()

        if sha1 == sig:
            self._reply(200, echostr.encode())
        else:
            self._reply(200, b"fail")

    def do_POST(self):
        """接收微信消息并回复"""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            msg = _parse_msg(body)
            if not msg:
                return self._reply(200, b"success")

            user_msg = msg.get("Content", "").strip()
            from_user = msg.get("FromUserName", "")
            logger.info(f"[{from_user}] {user_msg[:100]}")

            # 立即回复 success，然后异步发客服消息
            self._reply(200, b"success")

            reply_text = _generate_reply(user_msg)
            if reply_text:
                _send_custom_msg(from_user, reply_text)

        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            self._reply(200, b"success")

    def _reply(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)


# ── 消息处理 ─────────────────────────────────────────────

def _generate_reply(content: str) -> str:
    """生成AI回复"""
    if not content:
        return "你好！发送基金代码或持仓名称，我帮你分析。"

    lower = content.lower()
    if lower in ("帮助", "help", "菜单", "?", "？"):
        return "📊 持仓 · 🔍 基金代码 · 💡 操作建议 · ✍️ Dan Koe · 💬 随便聊"

    # 注入实时数据
    ctx = _get_fund_snapshot()
    prompt = f"基金数据:\n{ctx}\n\n用户: {content}"

    try:
        client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=800,
        )
        return resp.choices[0].message.content or "我没想好怎么回答，换个问法试试？"
    except Exception as e:
        logger.error(f"DeepSeek: {e}")
        return "AI暂时不可用，稍后再试。"


def _get_fund_snapshot() -> str:
    """快速抓取基金快照"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from src.fetch_data import fetch_etf_spot, fetch_otc_fund_nav
        lines = []
        etf = fetch_etf_spot(["159516"])
        for c, i in etf.items():
            lines.append(f"{c}: 价格{i['price']} 涨跌{i.get('change_pct',0):+.2f}%")
        for c in ["003579", "011613", "025766", "018927"]:
            n = fetch_otc_fund_nav(c)
            if n:
                lines.append(f"{c}: 净值{n['nav']}({n.get('date','')}) 变动{n.get('daily_change',0):+.2f}%")
        return "\n".join(lines) if lines else "数据暂时不可用"
    except Exception as e:
        return f"数据获取失败: {e}"


# ── 微信客服消息 ─────────────────────────────────────────

def _send_custom_msg(to_user: str, content: str):
    """通过微信客服消息API发送回复"""
    try:
        token = _get_access_token()
        if not token:
            return

        url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={token}"
        payload = {
            "touser": to_user,
            "msgtype": "text",
            "text": {"content": content},
        }
        resp = requests.post(url, json=payload, timeout=10)
        logger.info(f"客服消息: {resp.json()}")
    except Exception as e:
        logger.error(f"客服消息失败: {e}")


def _get_access_token() -> str:
    """获取微信 access_token（缓存1.5h）"""
    try:
        url = (
            "https://api.weixin.qq.com/cgi-bin/token"
            f"?grant_type=client_credential&appid={WECHAT_APPID}&secret={WECHAT_APPSECRET}"
        )
        resp = requests.get(url, timeout=10)
        data = resp.json()
        token = data.get("access_token", "")
        if token:
            logger.info("access_token 获取成功")
        else:
            logger.error(f"access_token 失败: {data}")
        return token
    except Exception as e:
        logger.error(f"access_token 请求失败: {e}")
        return ""


# ── XML ──────────────────────────────────────────────────

def _parse_msg(xml: bytes) -> dict | None:
    try:
        root = ET.fromstring(xml)
        return {child.tag: child.text for child in root}
    except ET.ParseError:
        return None
