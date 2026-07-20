"""
Vercel Flask 微信机器人
访问路径: /api/wechat
"""

import hashlib
import os
import time
import xml.etree.ElementTree as ET

from flask import Flask, request
from openai import OpenAI

app = Flask(__name__)

TOKEN = os.getenv("WECHAT_TOKEN", "investment_bot_token_2026")
DS = os.getenv("DEEPSEEK_API_KEY", "")

AI = OpenAI(api_key=DS, base_url="https://api.deepseek.com")

SP = """你是激进风格微信投资助手，服务一位学生（总资金~5万，生活压力小）。
持仓：159516半导体设备ETF(计划2万未建仓)、003579沪深300(9500)、011613科创50(1400)、025766港股通互联网(12600)、018927电池(7300)。
回复要求：先结论后理由，200-400字，干净排版，不确定就老实说。"""  # noqa: E501


@app.route("/", methods=["GET", "POST"])
def handler():
    if request.method == "GET":
        return _verify()

    try:
        xml = request.data
        msg = {c.tag: c.text for c in ET.fromstring(xml)}
        frm = msg.get("FromUserName", "")
        to = msg.get("ToUserName", "")
        text = msg.get("Content", "").strip()

        reply = _chat(text)

        return (
            "<xml>"
            f"<ToUserName><![CDATA[{frm}]]></ToUserName>"
            f"<FromUserName><![CDATA[{to}]]></FromUserName>"
            f"<CreateTime>{int(time.time())}</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            f"<Content><![CDATA[{reply}]]></Content>"
            "</xml>"
        )
    except Exception as e:
        return f"success<!--{e}-->"


def _verify() -> str:
    args = request.args
    tmp = sorted([TOKEN, args.get("timestamp", ""), args.get("nonce", "")])
    sha = hashlib.sha1("".join(tmp).encode()).hexdigest()
    return args.get("echostr", "") if sha == args.get("signature", "") else "fail"


def _chat(msg: str) -> str:
    if not msg:
        return "你好！试试问我：\n📊 持仓分析\n🔍 159516分析\n💡 操作建议\n✍️ Dan Koe"
    try:
        r = AI.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": SP}, {"role": "user", "content": msg}],
            temperature=0.7,
            max_tokens=800,
        )
        return r.choices[0].message.content or "换个问法试试？"
    except Exception as e:
        return f"AI暂时不可用 {str(e)[:50]}"
