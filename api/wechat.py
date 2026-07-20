"""
Vercel Flask 微信机器人
收消息 → 后台线程(AI分析→客服消息回复) → 主线程秒回success
"""

import hashlib
import os
import threading
import time
import xml.etree.ElementTree as ET

import requests
from flask import Flask, request
from openai import OpenAI

app = Flask(__name__)

TOKEN = os.getenv("WECHAT_TOKEN", "investment_bot_token_2026")
AID = os.getenv("WECHAT_APPID", "")
ASEC = os.getenv("WECHAT_APPSECRET", "")
DS = os.getenv("DEEPSEEK_API_KEY", "")

AI = OpenAI(api_key=DS, base_url="https://api.deepseek.com")

SP = """你是激进风格微信投资助手，服务一位学生（总资金~5万，生活压力小）。
持仓：159516半导体设备ETF(计划2万未建仓)、003579沪深300(9500)、011613科创50(1400)、025766港股通互联网(12600)、018927电池(7300)。
回复：先结论后理由，200-400字，干净排版，不确定就老实说。"""  # noqa: E501

# access_token 缓存
_token_cache = {"token": "", "expires": 0}


@app.route("/", methods=["GET", "POST"])
def handler():
    if request.method == "GET":
        args = request.args
        tmp = sorted([TOKEN, args.get("timestamp", ""), args.get("nonce", "")])
        sha = hashlib.sha1("".join(tmp).encode()).hexdigest()
        return args.get("echostr", "") if sha == args.get("signature", "") else "fail"

    # POST: 秒回success，后台线程处理
    try:
        xml = request.data
        msg = {c.tag: c.text for c in ET.fromstring(xml)}
        frm = msg.get("FromUserName", "")
        text = msg.get("Content", "").strip()

        t = threading.Thread(target=_process, args=(frm, text), daemon=True)
        t.start()

    except Exception:
        pass

    return "success"


def _process(to_user: str, msg: str):
    """后台线程：AI分析 + 客服消息推送"""
    reply = _chat(msg)
    if reply:
        _push(to_user, reply)


def _chat(msg: str) -> str:
    if not msg:
        return "你好！试试问我：\n📊 持仓分析\n🔍 159516分析\n💡 操作建议"
    if msg.strip() == "ping":
        return "pong ✅ 后台线程链路正常"
    try:
        r = AI.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": SP}, {"role": "user", "content": msg}],
            temperature=0.7, max_tokens=800,
        )
        return r.choices[0].message.content or "换个问法试试？"
    except Exception as e:
        return f"AI暂不可用 {str(e)[:50]}"


def _push(to: str, text: str):
    """微信客服消息推送"""
    tok = _get_token()
    if not tok:
        return
    try:
        url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={tok}"
        requests.post(url, json={"touser": to, "msgtype": "text", "text": {"content": text}}, timeout=10)
    except Exception:
        pass


def _get_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires"]:
        return _token_cache["token"]
    try:
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={AID}&secret={ASEC}"
        r = requests.get(url, timeout=10).json()
        tok = r.get("access_token", "")
        if tok:
            _token_cache["token"] = tok
            _token_cache["expires"] = now + 7000  # 2小时
        return tok
    except Exception:
        return ""
