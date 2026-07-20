"""Vercel 微信机器人 — api/index.py"""
import hashlib, os, time, xml.etree.ElementTree as ET
from flask import Flask, request

app = Flask(__name__)
TOKEN = os.getenv("WECHAT_TOKEN", "investment_bot_token_2026")


@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def h(path):
    if request.method == "GET":
        a = request.args
        tmp = sorted([TOKEN, a.get("timestamp", ""), a.get("nonce", "")])
        sha = hashlib.sha1("".join(tmp).encode()).hexdigest()
        return a.get("echostr", "") if sha == a.get("signature", "") else "fail"

    try:
        msg = {c.tag: c.text for c in ET.fromstring(request.data)}
        frm = msg.get("FromUserName", "")
        to = msg.get("ToUserName", "")
        txt = msg.get("Content", "empty")
        return (
            "<xml>"
            f"<ToUserName><![CDATA[{frm}]]></ToUserName>"
            f"<FromUserName><![CDATA[{to}]]></FromUserName>"
            f"<CreateTime>{int(time.time())}</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            f"<Content><![CDATA[ECHO: {txt[:100]}  path={path}]]></Content>"
            "</xml>"
        )
    except Exception as e:
        return f"success<!--{e}-->"
