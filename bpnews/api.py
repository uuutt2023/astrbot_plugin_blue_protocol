# -*- coding: utf-8 -*-
"""Blue Protocol: Star Resonance 官方公告数据层：调腾讯游戏官网的 wmp/v3.1 接口。

两个接口都返回 JSONP（``var XXX = {...};``），本模块负责剥壳成 dict：

- 列表：``/wmp/v3.1/?p0=440&p1=searchNewsKeywordsList&page=N&pagesize=M``
  取 ``msg.result``（每条含标题/时间/封面/分类标签 id），``msg.total`` 是总条数。
- 详情：``/wmp/v3.1/public/searchNews.php?p0=440&source=web_pc&id=<iNewsId>``
  取 ``msg.sContent``（正文 HTML）、``msg.sTitle``、``msg.sIMG``（封面）。

官网前台（gm.qq.com/web202503/news-list.html）里写死了分类标签表，这里照抄一份：
``136243=最新`` ``136246=公告`` ``136245=新闻`` ``136247=活动``。
列表接口用 ``type=iTag&id=<标签id>`` 过滤，所以既能取「最新」聚合流，也能只取某一类。
展示名统一用英文（插件整体以 Blue Protocol: Star Resonance 命名）。

这一层不 import astrbot，可以脱离 AstrBot 直接单测。
"""

from __future__ import annotations

import html as html_lib
import json
import re
from typing import Any
from urllib.parse import urlencode

GAME_ID = 440
SOURCE = "web_pc"

LIST_API = "https://apps.game.qq.com/wmp/v3.1/"
DETAIL_API = "https://apps.game.qq.com/wmp/v3.1/public/searchNews.php"
# 官网详情页（给人看的），插件给的「原文链接」用它
ARTICLE_PAGE = "https://gm.qq.com/web202503/news-detail.html"

# 官网 news-list.html 里的 newsTagList
TAG_ALL = "136243"
TAG_NAMES: dict[str, str] = {
    "136243": "Latest",
    "136246": "Notice",
    "136245": "News",
    "136247": "Event",
    "136244": "General",
}
# 展示用中文分类名（官网就叫最新 / 公告 / 新闻 / 活动 / 综合）。
# 指令参数仍然是英文（``bp list notice``），那是 NAME_TO_TAG 管的。
TAG_NAMES_ZH: dict[str, str] = {
    "136243": "最新",
    "136246": "公告",
    "136245": "新闻",
    "136247": "活动",
    "136244": "综合",
}
# 英文分类名 → 标签 id（给指令用）。别名多写几个，手滑也认得出来。
NAME_TO_TAG: dict[str, str] = {
    "all": TAG_ALL,
    "latest": TAG_ALL,
    "notice": "136246",
    "announcement": "136246",
    "announcements": "136246",
    "ann": "136246",
    "news": "136245",
    "event": "136247",
    "events": "136247",
    "activity": "136247",
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

_TAG_RE = re.compile(r"<[^>]*>")
_BR_RE = re.compile(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>")
_WS_RE = re.compile(r"[ \t\u3000]+")
_NL_RE = re.compile(r"\n{3,}")

# 招呼语开头（正文第一句常是「冒险者，您好！」），做摘要时跳过
_GREET_RE = re.compile(r"^\s*(?:冒险者|亲爱的|尊敬的|敬爱的|各位|玩家)?\s*[，,：:]?\s*(?:您|你)?\s*好[！!。.]?\s*")
_GREET_WORDS = ("冒险者", "亲爱的", "尊敬的", "敬爱的", "各位", "大家好", "您好", "你好")


# ---------------------------------------------------------------------------
# JSONP 剥壳
# ---------------------------------------------------------------------------


def extract_json_object(text: str) -> str:
    """从 ``var X = {...};`` 里抠出 JSON 对象文本。

    用括号配对扫描（字符串里的花括号不算），比正则稳 —— 正文里的
    ``sCoverMap`` 是转义后的 JSON 字符串，正则贪心/非贪婪都可能切错。
    """
    start = text.find("{")
    if start < 0:
        raise ValueError("响应里没有 JSON 对象")
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("JSON 对象没有闭合")


def parse_jsonp(text: str) -> dict[str, Any]:
    """JSONP → dict。解析失败时抛 ValueError。"""
    if not text or not text.strip():
        raise ValueError("响应为空")
    raw = extract_json_object(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("响应结构异常：顶层不是对象")
    return data


def _msg_of(payload: dict[str, Any]) -> dict[str, Any]:
    """取 msg 段。接口把正文放在 ``msg`` 里，``data`` 段是空的。"""
    msg = payload.get("msg")
    if isinstance(msg, dict):
        return msg
    if isinstance(payload.get("data"), dict):
        return payload["data"]
    return {}


# ---------------------------------------------------------------------------
# URL 拼装
# ---------------------------------------------------------------------------


def build_list_url(page: int = 1, page_size: int = 10, tag_id: str = TAG_ALL) -> str:
    """列表接口 URL。``page`` 是分页页码，从 1 开始。"""
    query = {
        "p0": GAME_ID,
        "p1": "searchNewsKeywordsList",
        "page": max(1, int(page)),
        "pagesize": max(1, int(page_size)),
        "order": "sIdxTime",
        "r0": "script",
        "r1": "NewsObj5014741213624121",
        "type": "iTag",
        "id": str(tag_id),
        "source": SOURCE,
    }
    return f"{LIST_API}?{urlencode(query)}"


def build_detail_url(news_id: str | int) -> str:
    """详情接口 URL（JSON，用正文 HTML）。"""
    query = {"p0": GAME_ID, "source": SOURCE, "id": str(news_id)}
    return f"{DETAIL_API}?{urlencode(query)}"


def article_url(news_id: str | int) -> str:
    """官网详情页 URL（人看的，给「原文链接」）。"""
    return f"{ARTICLE_PAGE}?newsid={news_id}"


def resolve_tag(name: str) -> str:
    """英文分类名 → 标签 id。认不出来返回空串（调用方走默认的「全部」）。"""
    return NAME_TO_TAG.get(str(name or "").strip().lower(), "")


def tag_display_name(tag_id: str) -> str:
    """标签 id → 中文展示名（最新 / 公告 / 新闻 / 活动 / 综合）。"""
    return TAG_NAMES_ZH.get(str(tag_id or "").strip(), "")


# ---------------------------------------------------------------------------
# 字段归一
# ---------------------------------------------------------------------------


def normalize_cover(url: str) -> str:
    """封面图 URL 补全协议头。

    接口给的是 ``//static.gametalk.qq.com/...`` 这种协议相对地址，
    直接丢给 QQ 会拒绝，得补成 https。
    """
    text = str(url or "").strip()
    if not text:
        return ""
    if text.startswith("//"):
        return "https:" + text
    if text.startswith(("http://", "https://")):
        return text
    if text.startswith("/"):
        return "https://static.gametalk.qq.com" + text
    return "https://static.gametalk.qq.com/" + text


def tag_label(tag_ids: str) -> str:
    """``sTagIds``（可能是 ``136245,136244``）→ 分类名。认不出来就给空串。"""
    names: list[str] = []
    for raw in str(tag_ids or "").split(","):
        key = raw.strip()
        if not key:
            continue
        name = TAG_NAMES_ZH.get(key, "")
        if name and name not in names:
            names.append(name)
    return "/".join(names)


def parse_list_item(raw: dict[str, Any]) -> dict[str, Any]:
    """列表项 → 插件内部结构。"""
    news_id = str(raw.get("iNewsId") or "").strip()
    title = str(raw.get("sTitle") or "").strip()
    if not news_id or not title:
        return {}
    cover = normalize_cover(raw.get("sIMG") or "")
    return {
        "news_id": news_id,
        "title": title,
        "time": str(raw.get("sIdxTime") or raw.get("sCreated") or "").strip(),
        "desc": str(raw.get("sDesc") or "").strip() or title,
        "cover": cover,
        "tag": tag_label(raw.get("sTagIds")),
        "url": article_url(news_id),
    }


def parse_detail(raw: dict[str, Any]) -> dict[str, Any]:
    """详情段 → 插件内部结构。"""
    news_id = str(raw.get("iNewsId") or "").strip()
    title = str(raw.get("sTitle") or "").strip()
    content = str(raw.get("sContent") or "")
    if not title and not content:
        return {}
    return {
        "news_id": news_id,
        "title": title,
        "time": str(raw.get("sIdxTime") or raw.get("sCreated") or "").strip(),
        "desc": str(raw.get("sDesc") or "").strip(),
        "cover": normalize_cover(raw.get("sIMG") or ""),
        "tag": tag_label(raw.get("sTagIds")),
        "content": content,
        "url": article_url(news_id) if news_id else "",
    }


# ---------------------------------------------------------------------------
# HTML → 纯文本
# ---------------------------------------------------------------------------


def html_to_text(html: str) -> str:
    """正文 HTML → 纯文本。

    ``<br>`` / ``</p>`` 这类块级闭合标签换成换行，其余标签直接去掉；
    HTML 实体（``&ldquo;`` ``&times;`` ``&nbsp;``）用标准实体表还原。
    """
    text = str(html or "")
    if not text.strip():
        return ""
    text = _BR_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    text = html_lib.unescape(text)
    text = text.replace("\xa0", " ")
    text = _WS_RE.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return _NL_RE.sub("\n\n", "\n".join(lines)).strip()


def summarize(html: str, limit: int = 200) -> str:
    """从正文 HTML 里取一段摘要（跳过「冒险者，您好！」这类招呼语）。"""
    text = html_to_text(html)
    if not text:
        return ""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    body = ""
    for line in lines:
        if len(line) < 12 and any(word in line for word in _GREET_WORDS):
            continue  # 招呼语，无信息量
        body = line
        break
    if not body:
        body = lines[0] if lines else ""
    body = _GREET_RE.sub("", body).strip() or body
    if len(body) <= limit:
        return body
    return body[:limit].rstrip() + "…"


# ---------------------------------------------------------------------------
# 网络请求
# ---------------------------------------------------------------------------


async def _http_get(url: str, timeout: float = 15) -> str:
    import httpx

    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": UA, "Referer": "https://gm.qq.com/"},
        follow_redirects=True,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


async def fetch_list(
    page: int = 1, page_size: int = 10, tag_id: str = TAG_ALL
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """拉一页公告。返回 (条目列表, 分页信息)。

    分页信息：``{page, pagesize, total, totalpage}``。
    """
    url = build_list_url(page=page, page_size=page_size, tag_id=tag_id)
    payload = parse_jsonp(await _http_get(url))
    msg = _msg_of(payload)
    raw_items = msg.get("result")
    if not isinstance(raw_items, list):
        raw_items = []
    items = [parse_list_item(it) for it in raw_items if isinstance(it, dict)]
    items = [it for it in items if it]
    info = {
        "page": _as_int(msg.get("page"), page),
        "pagesize": _as_int(msg.get("pagesize"), page_size),
        "total": _as_int(msg.get("total"), len(items)),
        "totalpage": _as_int(msg.get("totalpage"), 1),
    }
    return items, info


async def fetch_detail(news_id: str | int) -> dict[str, Any]:
    """拉一条公告的正文。拿不到内容时返回空 dict（不抛异常）。"""
    url = build_detail_url(news_id)
    payload = parse_jsonp(await _http_get(url))
    return parse_detail(_msg_of(payload))


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
