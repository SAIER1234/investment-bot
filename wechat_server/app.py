"""
微信公众号测试号 — Flask 服务器
接收用户消息 → DeepSeek 回复 → 返回微信
"""

import hashlib
import logging
import os
import sys
import time
from datetime import datetime

from flask import Flask, request, Response

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chat import chat_reply
from tools import get_fund_context

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wechat")


# ── 微信签名验证 ─────────────────────────────────────────

WECHAT_TOKEN = os.getenv("WECHAT_TOKEN", "investment_bot_token_2026")


@app.route("/wechat", methods=["GET", "POST"])
def wechat():
    if request.method == "GET":
        return _verify_signature()

    # POST: 接收消息
    try:
        xml_data = request.data
        msg = _parse_msg(xml_data)
        if not msg:
            return "success"

        logger.info(f"[{msg.get('FromUserName','')}] {msg.get('Content','')[:100]}")

        # 生成回复
        reply_text = _handle_message(msg)

        # 返回 XML 回复（微信5秒超时内）
        return Response(
            _build_reply_xml(msg, reply_text),
            content_type="application/xml; charset=utf-8",
        )
    except Exception as e:
        logger.error(f"处理消息失败: {e}")
        return "success"


def _verify_signature() -> str:
    """微信服务器配置验证 (GET)"""
    signature = request.args.get("signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")
    echostr = request.args.get("echostr", "")

    tmp = sorted([WECHAT_TOKEN, timestamp, nonce])
    sha1 = hashlib.sha1("".join(tmp).encode()).hexdigest()

    if sha1 == signature:
        return echostr
    return "fail"


# ── 消息处理 ─────────────────────────────────────────────

def _handle_message(msg: dict) -> str:
    """根据用户消息生成回复"""
    content = msg.get("Content", "").strip()
    if not content:
        return "你好！有什么可以帮你的？"

    # 特殊指令
    lower = content.lower()
    if lower in ("帮助", "help", "?", "？", "菜单"):
        return _help_text()

    if any(w in content for w in ("持仓", "组合", "我的基金")):
        return _with_context(content, "用户询问持仓组合情况，请基于数据给出分析。")

    if any(w in content for w in ("建议", "操作", "加仓", "减仓", "买入", "卖出")):
        return _with_context(content, "用户询问操作建议，请给出明确的判断和操作方案。")

    # 基金代码
    for code in ["159516", "003579", "011613", "025766", "018927"]:
        if code in content:
            return _with_context(content, f"用户询问基金 {code}，请基于数据深度分析。")

    # 通用对话
    try:
        reply = chat_reply(content)
        return reply or "抱歉，我没理解你的问题。试试发送「帮助」看看我能做什么？"
    except Exception:
        return "AI 暂时无法响应，请稍后再试。"


def _with_context(user_msg: str, instruction: str) -> str:
    """注入最新基金数据后让 AI 回答"""
    try:
        ctx = get_fund_context()
        prompt = f"{instruction}\n\n基金数据:\n{ctx}\n\n用户问题: {user_msg}"
        return chat_reply(prompt) or "AI 分析失败，请稍后再试。"
    except Exception as e:
        logger.error(f"上下文查询失败: {e}")
        try:
            return chat_reply(user_msg) or "回复失败"
        except Exception:
            return "系统暂时不可用，请稍后再试。"


def _help_text() -> str:
    return (
        "🤖 我能帮你做什么？\n\n"
        "📊 发送「持仓」— 查看基金组合分析\n"
        "🔍 发送基金代码（如159516）— 深度分析单只基金\n"
        "💡 发送「建议」— 获取操作建议\n"
        "✍️ 发送「Dan Koe」— 查看最新博客摘要\n"
        "💬 也可以随便聊聊投资相关的问题"
    )


# ── XML 解析 ─────────────────────────────────────────────

def _parse_msg(xml: bytes) -> dict | None:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml)
        return {child.tag: child.text for child in root}
    except ET.ParseError:
        return None


def _build_reply_xml(msg: dict, content: str) -> str:
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{msg.get('FromUserName', '')}]]></ToUserName>"
        f"<FromUserName><![CDATA[{msg.get('ToUserName', '')}]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        "</xml>"
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
