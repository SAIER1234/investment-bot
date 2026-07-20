"""
公共基础设施
路径常量、代理禁用、日期格式化、JSON 读写 —— 一处定义，全项目引用。
"""

import json
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ── 路径常量 ───────────────────────────────────────────────
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT_DIR, "config")
DATA_DIR = os.path.join(ROOT_DIR, "data")


def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


# ── 代理禁用 ───────────────────────────────────────────────
def disable_proxy() -> None:
    """
    清除系统代理设置，防止 akshare 走 Windows 注册表代理（如 Clash）。
    在 import akshare 之前调用。
    """
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
        os.environ.pop(key, None)
    os.environ["no_proxy"] = "*"
    try:
        import urllib.request
        urllib.request.getproxies = lambda: {}
    except Exception:
        pass


# ── 日期工具 ───────────────────────────────────────────────
_WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def format_date_cn(dt: datetime | None = None) -> tuple[str, str]:
    """
    返回 (日期字符串, 星期字符串)
    例: ("2026年07月20日", "周一")
    """
    if dt is None:
        dt = datetime.now()
    date_str = dt.strftime("%Y年%m月%d日")
    weekday_str = _WEEKDAY_CN[dt.weekday()]
    return date_str, weekday_str


# ── JSON 工具 ──────────────────────────────────────────────
def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: dict[str, Any]) -> None:
    ensure_data_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
