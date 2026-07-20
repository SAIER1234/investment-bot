"""
AI 对话模块 — DeepSeek Chat
复用投资顾问角色，支持带上下文的多轮对话。
"""

import logging
import os

from openai import OpenAI

logger = logging.getLogger("chat")

SYSTEM_PROMPT = """你是一个微信投资助手，通过微信公众号和一位中国学生投资者对话。

关于用户：
- 学生，总资金约5万元，投资风格激进，生活压力小
- 持仓：003579 沪深300(9500元)、011613 科创50(1400元)、025766 港股通互联网(12600元)、018927 电池(7300元)、159516 半导体设备ETF(计划买入20000元)
- 用户希望你给明确的判断和操作建议，不要模棱两可

回复要求：
- 每条回复控制在手机两屏以内（200-400字）
- 先给结论，再说理由
- 排版干净，适当用emoji分隔板块
- 不确定的地方老实说出来
- 如果用户发基金代码，直接分析那支基金"""


def chat_reply(user_message: str, history: list[dict] | None = None) -> str:
    """单轮对话：用户消息 → AI 回复"""
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        return "系统配置错误：未设置 AI Key"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"DeepSeek 调用失败: {e}")
        return ""


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    reply = chat_reply("帮我看看159516现在能不能买")
    print(reply)
