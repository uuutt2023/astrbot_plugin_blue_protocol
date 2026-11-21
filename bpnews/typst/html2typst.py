# -*- coding: utf-8 -*-
"""公告正文 HTML → Typst 可排版的结构化段落。

真正的解析在 :mod:`bpnews.htmlblocks`（Typst 长图与 HTML 兜底长图共用），
这里保留一层薄封装，方便按 Typst 语境调用。
"""

from __future__ import annotations

from ..htmlblocks import classify, to_text


def html_to_blocks(html: str) -> list[dict]:
    """把公告正文 HTML 转成排版块。

    每块是 ``{"kind": "h1".."h4"|"p", "runs": [...]}`` 或
    ``{"kind": "img", "src": ..., "alt": ...}``。
    """
    return classify(html)


def html_to_text(html: str) -> str:
    """公告正文 HTML → 纯文本（摘要、面板展示用）。"""
    return to_text(classify(html))
