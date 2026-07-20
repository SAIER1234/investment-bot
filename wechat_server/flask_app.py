"""
PythonAnywhere Flask — 微信投资助手
GET /wechat  → 微信URL验证
POST /wechat → 收消息 → DeepSeek分析 → XML回复
"""

import hashlib
import logging
import os
import sys
import time

from flask import Flask, request
from openai import OpenAI

# 加项目根目录到 path，以便 import src.fetch_data
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
log = logging.getLogger("flask_wechat")

TOKEN = os.getenv("WECHAT_TOKEN", "investment_bot_token_2026")
DS_KEY = os.getenv("DEEPSEEK_API_KEY", "")

SYSTEM_PROMPT = """你是激进风格微信投资助手，服务一位学生（总资金~5万，生活压力小）。
用户实时持仓（参考）：
- 159516 半导体设备ETF国泰 计划买入20000元（尚未建仓）
- 003579 沪深300 持有9500元
- 011613 科创50 持有1400元
- 025766 港股通互联网 持有12600元
- 018927 电池 持有7300元

回复风格：先结论后理由，200-400字，干净排版，不确定的地方老实说。
如果用户问具体基金，帮他从估值、技术面、消息面、持仓逻辑四个角度分析。"""  # noqa: E501


@app.route("/wechat", methods=["GET", "POST"])
def wechat():
    if request.method == "GET":
        return _verify()

    # POST: 处理用户消息
    try:
        xml_data = request.data
        msg = _parse_xml(xml_data)
        if not msg:
            return "success"

        from_user = msg.get("FromUserName", "")
        to_user = msg.get("ToUserName", "")
        content = msg.get("Content", "").strip()
        log.info(f"[{from_user}] {content[:100]}")

        reply = _chat(content)
        return _build_reply(from_user, to_user, reply)

    except Exception as e:
        log.error(f"POST error: {e}")
        return "success"


def _verify():
    """微信URL验证"""
    args = request.args
    tmp = sorted([TOKEN, args.get("timestamp", ""), args.get("nonce", "")])
    sha1 = hashlib.sha1("".join(tmp).encode()).hexdigest()
    if sha1 == args.get("signature", ""):
        return args.get("echostr", "")
    return "fail"


def _chat(msg: str) -> str:
    """DeepSeek 生成回复"""
    if not msg:
        return "你好！试试问我：\n📊 持仓分析\n🔍 159516分析\n💡 操作建议\n✍️ Dan Koe"

    try:
        client = OpenAI(api_key=DS_KEY, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": msg},
            ],
            temperature=0.7,
            max_tokens=800,
        )
        return resp.choices[0].message.content or "我没想好，换个问法？"
    except Exception as e:
        log.error(f"DeepSeek error: {e}")
        return "AI暂时不可用，请稍后再试。"


def _parse_xml(xml: bytes) -> dict | None:
    import xml.etree.ElementTree as ET
    try:
        return {c.tag: c.text for c in ET.fromstring(xml)}
    except ET.ParseError:
        return None


def _build_reply(to_user: str, from_user: str, content: str) -> str:
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        "</xml>"
    )


# PythonAnywhere WSGI 入口
application = app
