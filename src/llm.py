"""
LLM 客户端工厂
统一管理 DeepSeek API 连接参数，analyze.py 和 digest_ai.py 共用。
内置 retry（3次，间隔2/4/8秒）+ timeout（120秒）。
"""

import logging
import os
import time

from openai import OpenAI, APITimeoutError, APIError, APIConnectionError

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-pro"

# 默认超参（各模块可覆盖）
DEFAULT_INVEST_TEMP = 0.7     # 投资报告
DEFAULT_INVEST_TOKENS = 8192  # 推理模型思考占token，输出预算要留足
DEFAULT_DIGEST_TEMP = 0.8     # 晨报摘要
DEFAULT_DIGEST_TOKENS = 2048

RETRIES = 3                   # 最多重试次数
RETRY_BASE_DELAY = 2          # 首次重试延迟（秒），指数递增：2, 4, 8


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
    """调用 DeepSeek Chat API，内置 retry + timeout。返回文本响应。"""
    last_error = None

    for attempt in range(RETRIES):
        try:
            client = create_deepseek_client(api_key)
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=240,
            )
            msg = response.choices[0].message
            # 只用正式content。reasoning_content是模型思考过程，绝不推送给用户
            content = msg.content or ''
            if content:
                return content
            logger.warning(f"第{attempt+1}次调用返回空content，重试")
            last_error = RuntimeError("DeepSeek返回空content")
        except (APITimeoutError, APIConnectionError) as e:
            last_error = e
            if attempt < RETRIES - 1:
                delay = RETRY_BASE_DELAY ** (attempt + 1)  # 2, 4, 8
                logger.warning(f"DeepSeek API 第{attempt+1}/{RETRIES}次失败，{delay}s后重试: {e}")
                time.sleep(delay)
        except APIError as e:
            # 非网络错误（401/429/500等），不重试，直接抛
            raise RuntimeError(f"DeepSeek API 错误: {e}") from e

    raise RuntimeError(f"DeepSeek API {RETRIES}次重试全部失败: {last_error}")
