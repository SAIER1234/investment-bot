"""
LLM 客户端工厂
统一管理 DeepSeek API 连接参数，analyze.py 和 digest_ai.py 共用。
"""

import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# 默认超参（各模块可覆盖）
DEFAULT_INVEST_TEMP = 0.7     # 投资报告
DEFAULT_INVEST_TOKENS = 4096
DEFAULT_DIGEST_TEMP = 0.8     # 晨报摘要
DEFAULT_DIGEST_TOKENS = 2048


def create_deepseek_client(api_key: str | None = None) -> OpenAI:
    """创建 DeepSeek API 客户端"""
    if api_key is None:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def call_deepseek(
    system_prompt: str,
    user_prompt: str,
    api_key: str | None = None,
    temperature: float = DEFAULT_INVEST_TEMP,
    max_tokens: int = DEFAULT_INVEST_TOKENS,
) -> str:
    """调用 DeepSeek Chat API，返回文本响应"""
    client = create_deepseek_client(api_key)
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""
