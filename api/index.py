"""Vercel 微信机器人 — api/index.py (Vercel默认入口)"""
import hashlib, os, threading, time, xml.etree.ElementTree as ET
import requests
from flask import Flask, request
from openai import OpenAI

app = Flask(__name__)
TOKEN = os.getenv("WECHAT_TOKEN", "investment_bot_token_2026")
AID = os.getenv("WECHAT_APPID", "")
ASEC = os.getenv("WECHAT_APPSECRET", "")
DS = os.getenv("DEEPSEEK_API_KEY", "")
AI = OpenAI(api_key=DS, base_url="https://api.deepseek.com")
SP = "你是激进风格微信投资助手，服务学生(总资金~5万)。持仓:159516半导体设备ETF(计划2万未建仓)、003579沪深300(9500)、011613科创50(1400)、025766港股通互联网(12600)、018927电池(7300)。先结论后理由，200-400字。"  # noqa
_token = {"v": "", "exp": 0}


@app.route("/", methods=["GET", "POST"])
def h():
    if request.method == "GET":
        a = request.args
        tmp = sorted([TOKEN, a.get("timestamp", ""), a.get("nonce", "")])
        sha = hashlib.sha1("".join(tmp).encode()).hexdigest()
        return a.get("echostr", "") if sha == a.get("signature", "") else "fail"
    try:
        msg = {c.tag: c.text for c in ET.fromstring(request.data)}
        threading.Thread(target=_proc, args=(msg.get("FromUserName", ""), msg.get("Content", "").strip()), daemon=True).start()
    except Exception:
        pass
    return "success"


def _proc(to, txt):
    r = _ai(txt)
    if r:
        _push(to, r)


def _ai(m):
    if not m: return "你好！📊持仓分析 🔍159516 💡操作建议"
    if m.strip() == "ping": return "pong 线程OK"
    try:
        r = AI.chat.completions.create(model="deepseek-chat", messages=[{"role": "system", "content": SP}, {"role": "user", "content": m}], temperature=0.7, max_tokens=800)
        return r.choices[0].message.content or ""
    except Exception as e:
        return f"AI暂不可用 {str(e)[:50]}"


def _push(to, text):
    t = _tok()
    if not t: return
    try:
        requests.post(f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={t}", json={"touser": to, "msgtype": "text", "text": {"content": text}}, timeout=10)
    except Exception:
        pass


def _tok():
    n = time.time()
    if _token["v"] and n < _token["exp"]: return _token["v"]
    try:
        r = requests.get(f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={AID}&secret={ASEC}", timeout=10).json()
        t = r.get("access_token", "")
        if t: _token["v"], _token["exp"] = t, n + 7000
        return t
    except Exception:
        return ""
