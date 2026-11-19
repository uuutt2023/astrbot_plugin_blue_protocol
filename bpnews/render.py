# -*- coding: utf-8 -*-
"""公告正文 → 长图 HTML（Blue Protocol: Star Resonance）。

``templates/article.html`` 里的占位符用最朴素的字符串替换填（不走模板引擎，
少一个依赖，也避免 Jinja2 把正文 HTML 转义掉）。标题/链接这些要转义，
正文 ``sContent`` 是接口给的 HTML，原样插进去。
"""

from __future__ import annotations

import html as html_lib
from pathlib import Path
from typing import Any

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
ARTICLE_TEMPLATE = _TEMPLATE_DIR / "article.html"
CARD_TEMPLATE = _TEMPLATE_DIR / "card.html"


def _read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(
            f"template missing: {path}. The plugin folder is incomplete, please reinstall the full zip"
        )
    return path.read_text(encoding="utf-8")


def _cover_block(cover: str) -> str:
    if not cover:
        return ""
    safe = html_lib.escape(cover, quote=True)
    return f'<img class="cover" src="{safe}" alt="">'


def render_article(detail: dict[str, Any]) -> str:
    """把公告详情 dict 渲染成整页 HTML（给 Playwright 截图用）。"""
    tmpl = _read(ARTICLE_TEMPLATE)
    title = str(detail.get("title") or "").strip()
    tag = str(detail.get("tag") or "").strip() or "公告"
    time_text = str(detail.get("time") or "").strip()
    url = str(detail.get("url") or "").strip()
    content = str(detail.get("content") or "").strip()
    cover = str(detail.get("cover") or "").strip()

    if not content:
        content = "<p>（这条公告没有正文内容，点击原文链接查看）</p>"

    replacements = {
        "{{TAG}}": f'<span class="tag">{html_lib.escape(tag)}</span>',
        "{{TITLE}}": html_lib.escape(title),
        "{{TIME}}": html_lib.escape(time_text),
        "{{COVER}}": _cover_block(cover),
        "{{CONTENT}}": content,
        "{{URL}}": html_lib.escape(url),
    }
    for key, value in replacements.items():
        tmpl = tmpl.replace(key, value)
    return tmpl


def card_data(item: dict[str, Any], summary: str) -> dict[str, Any]:
    """兜底卡片图的数据（AstrBot html_render 用，走 Jinja2）。"""
    return {
        "tag": str(item.get("tag") or "公告"),
        "title": str(item.get("title") or ""),
        "time": str(item.get("time") or ""),
        "url": str(item.get("url") or ""),
        "desc": str(summary or ""),
    }
