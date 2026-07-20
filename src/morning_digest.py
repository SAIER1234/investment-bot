"""
晨间晨报 — 内容抓取模块
从博客 RSS 和 Nitter RSS 获取最近内容。
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree

import feedparser
import requests

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT_DIR, "config")
DATA_DIR = os.path.join(ROOT_DIR, "data")


def load_sources() -> dict[str, Any]:
    path = os.path.join(CONFIG_DIR, "sources.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 博客 RSS ─────────────────────────────────────────────

def fetch_blog_posts(blog: dict[str, Any], max_items: int = 3,
                     lookback_hours: int = 48) -> list[dict[str, Any]]:
    """抓取单个博客的最近文章"""
    try:
        feed = feedparser.parse(blog["url"])
        posts = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        for entry in feed.entries[:max_items]:
            pub_date = _parse_date(entry)
            if pub_date and pub_date < cutoff:
                continue

            posts.append({
                "source": blog["name"],
                "source_type": "blog",
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "summary": _clean_html(entry.get("summary", entry.get("description", ""))),
                "published": pub_date.isoformat() if pub_date else "",
                "language": blog.get("language", "en"),
                "description": blog.get("description", ""),
            })

        logger.info(f"[{blog['name']}] {len(posts)} new posts")
        return posts
    except Exception as e:
        logger.error(f"[{blog['name']}] RSS 抓取失败: {e}")
        return []


# ── Twitter（通过 Nitter RSS） ────────────────────────────

def fetch_tweets(handle_info: dict[str, Any], nitter_instance: str,
                 max_items: int = 3, lookback_hours: int = 48) -> list[dict[str, Any]]:
    """通过 Nitter RSS 获取用户最近推文"""
    handle = handle_info["handle"]
    url = f"{nitter_instance}/{handle}/rss"
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "MorningDigest/1.0"})
        if resp.status_code != 200:
            logger.warning(f"[@{handle}] Nitter 返回 {resp.status_code}")
            return []

        feed = feedparser.parse(resp.text.encode("utf-8") if isinstance(resp.text, str) else resp.text)
        tweets = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        for entry in feed.entries[:max_items]:
            pub_date = _parse_date(entry)
            if pub_date and pub_date < cutoff:
                continue

            # Nitter RSS title 格式: "username: tweet content"
            title = entry.get("title", "")
            content = title.split(":", 1)[-1].strip() if ":" in title else title

            tweets.append({
                "source": handle_info["name"],
                "source_type": "twitter",
                "handle": handle,
                "title": content[:100],
                "url": entry.get("link", f"https://twitter.com/{handle}"),
                "summary": content,
                "published": pub_date.isoformat() if pub_date else "",
                "language": handle_info.get("language", "en"),
                "description": handle_info.get("description", ""),
            })

        logger.info(f"[@{handle}] {len(tweets)} new tweets")
        return tweets
    except requests.RequestException as e:
        logger.error(f"[@{handle}] Nitter 连接失败: {e}")
        return []
    except Exception as e:
        logger.error(f"[@{handle}] 解析失败: {e}")
        return []


# ── 主入口 ────────────────────────────────────────────────

def fetch_all() -> list[dict[str, Any]]:
    """抓取所有来源的最新内容，返回统一格式列表"""
    sources = load_sources()
    settings = sources.get("settings", {})
    max_items = settings.get("max_items_per_source", 3)
    lookback = settings.get("lookback_hours", 48)
    nitter = settings.get("nitter_instance", "https://nitter.net")

    all_items: list[dict[str, Any]] = []

    # 博客
    for blog in sources.get("blogs", []):
        posts = fetch_blog_posts(blog, max_items=max_items, lookback_hours=lookback)
        all_items.extend(posts)

    # Twitter
    for handle in sources.get("twitter_handles", []):
        tweets = fetch_tweets(handle, nitter, max_items=max_items, lookback_hours=lookback)
        all_items.extend(tweets)

    logger.info(f"Total: {len(all_items)} items from {len(sources.get('blogs',[]))} blogs + {len(sources.get('twitter_handles',[]))} Twitter handles")
    return all_items


# ── 工具 ─────────────────────────────────────────────────

def _parse_date(entry: Any) -> datetime | None:
    """解析 RSS 条目的发布日期"""
    for attr in ("published_parsed", "updated_parsed"):
        tp = getattr(entry, attr, None)
        if tp:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(tp), tz=timezone.utc)
            except Exception:
                pass
    # 尝试字符串格式
    for attr in ("published", "updated"):
        s = getattr(entry, attr, None)
        if s:
            try:
                from email.utils import parsedate_to_datetime
                return parsedate_to_datetime(s)
            except Exception:
                pass
    return None


def _clean_html(text: str, max_len: int = 300) -> str:
    """移除 HTML 标签，截取摘要"""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_len:
        clean = clean[:max_len] + "..."
    return clean


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    items = fetch_all()
    for item in items:
        print(f"[{item['source']}] {item['title'][:80]}")
