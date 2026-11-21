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

from . import htmlblocks, layout

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


def _style_css(spec: dict[str, Any]) -> str:
    """把版式表转成 CSS 变量（和 Typst 长图同一份定义）。"""
    colors = spec["colors"]
    type_scale = spec["type"]
    def px(value: float) -> str:
        """整数值不要小数尾巴（17 而不是 17.0）。"""
        number = float(value)
        return f"{int(number)}px" if number.is_integer() else f"{round(number, 2)}px"

    values = {
        "--page-w": f"{spec['width']}px",
        "--body-w": f"{spec['body']}px",
        "--border": f"{spec['border']}px",
        "--para-gap": px(spec["para_spacing"]),
        "--line-height": str(spec["line_height"]),
        "--module-gap": px(spec["module_spacing"]),
        "--banner-h": px(type_scale["banner"]),
        "--pad-top": px(type_scale["pad_top"]),
        "--font-tag": px(type_scale["font_tag"]),
        "--font-title": px(type_scale["font_title"]),
        "--font-meta": px(type_scale["font_meta"]),
        "--font-body": px(type_scale["font_body"]),
        "--font-h2": px(type_scale["font_h2"]),
        "--font-h3": px(type_scale["font_h3"]),
        "--font-link": px(type_scale["font_link"]),
        "--font-foot": px(type_scale["font_foot"]),
    }
    for key, value in colors.items():
        values[f"--{key.replace('_', '-')}"] = value
    return "\n".join(f"  {key}: {value};" for key, value in values.items())


def render_article(detail: dict[str, Any], **layout_options: Any) -> str:
    """把公告详情 dict 渲染成整页 HTML（给 Playwright 截图用）。

    正文不是原样塞进去的，而是和 Typst 长图共用 :mod:`bpnews.htmlblocks`
    的解析结果 —— 同样的模块划分、同样的留白，两条路长得一样。

    ``layout_options`` 接受画布宽度/正文宽度/边框/主题/段间距/行高/模块间距，
    缺省时用 :mod:`bpnews.layout` 的默认值。
    """
    tmpl = _read(ARTICLE_TEMPLATE)
    title = str(detail.get("title") or "").strip()
    tag = str(detail.get("tag") or "").strip() or "公告"
    time_text = str(detail.get("time") or "").strip()
    url = str(detail.get("url") or "").strip()
    raw_content = str(detail.get("content") or "").strip()
    cover = str(detail.get("cover") or "").strip()

    spec = layout.resolve(**layout_options)

    blocks = layout.apply_gaps(
        htmlblocks.classify(raw_content),
        para_spacing=spec["para_spacing"],
        module_spacing=spec["module_spacing"],
    )
    content = htmlblocks.to_html(blocks)
    if not content:
        content = "<p>（这条公告没有正文内容，点击原文链接查看）</p>"

    replacements = {
        "{{TAG}}": f'<span class="tag">{html_lib.escape(tag)}</span>',
        "{{TITLE}}": html_lib.escape(title),
        "{{TIME}}": html_lib.escape(time_text),
        "{{COVER}}": _cover_block(cover),
        "{{CONTENT}}": content,
        "{{URL}}": html_lib.escape(url),
        "{{STYLE}}": _style_css(spec),
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
