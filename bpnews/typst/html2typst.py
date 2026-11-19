# -*- coding: utf-8 -*-
"""公告正文 HTML → Typst 可排版的结构化段落。

《星痕共鸣》的公告正文由接口直接给 HTML（``msg.sContent``），结构很简单：
``<p>`` 段落、``<br/>`` 换行、少量 ``<b>``/``<i>`` 内联标签和 HTML 实体。

Typst 不吃 HTML，这里把 HTML 拆成「段落 → 行内片段」两级结构，正文交给
Typst 模板排版。片段文本原样写进 JSON：Typst 里的字符串是**纯文本**，不会被
再次当成标记解析，所以正文中的 ``#``、``*``、``_``、``\\`` 都不需要转义。
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

# 会结束当前段落的块级标签
_BLOCK_TAGS = {
    "p", "div", "section", "article", "blockquote", "header", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "tr", "table",
    "tbody", "thead", "tfoot", "dl", "dd", "dt", "pre", "figure",
}
_BOLD_TAGS = {"b", "strong"}
_ITALIC_TAGS = {"i", "em"}
_UNDERLINE_TAGS = {"u", "ins"}
_STRIKE_TAGS = {"s", "del", "strike"}
# 这些标签的内容直接丢掉（正文里不该出现）
_SKIP_TAGS = {"script", "style", "head", "title", "noscript", "iframe"}
# 表格行内的单元格分隔，展开成竖线
_CELL_TAGS = {"td", "th"}
# 实体里的不换行空格，统一成普通空格（Typst 里用 ~ 排版更稳）
_NBSP = re.compile("\xa0")


class _BodyParser(HTMLParser):
    """把公告正文 HTML 拆成段落与行内片段。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict] = []
        self._runs: list[dict] = []
        self._bold = 0
        self._italic = 0
        self._underline = 0
        self._strike = 0
        self._skip = 0
        self._pending_break = False

    # -- 内部 -------------------------------------------------------------

    def _flush(self) -> None:
        """把当前段落收尾，空段落丢掉。"""
        if not self._runs:
            return
        if any(not r.get("br") and r.get("t") for r in self._runs):
            self.blocks.append({"runs": self._runs})
        self._runs = []

    def _append_text(self, text: str) -> None:
        if self._skip or not text:
            return
        text = _NBSP.sub(" ", text)
        if not text:
            return
        bold = self._bold > 0
        italic = self._italic > 0
        underline = self._underline > 0
        strike = self._strike > 0
        if self._runs:
            last = self._runs[-1]
            if (
                not last.get("br")
                and last.get("b", False) == bold
                and last.get("i", False) == italic
                and last.get("u", False) == underline
                and last.get("s", False) == strike
            ):
                last["t"] += text
                return
        self._runs.append(
            {"t": text, "b": bold, "i": italic, "u": underline, "s": strike}
        )

    def _append_break(self) -> None:
        if self._skip:
            return
        if self._runs and not self._runs[-1].get("br"):
            self._runs.append({"br": True})

    # -- HTMLParser 回调 --------------------------------------------------

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "br":
            self._append_break()
            return
        if tag in _BLOCK_TAGS:
            self._flush()
            return
        if tag in _BOLD_TAGS:
            self._bold += 1
        elif tag in _ITALIC_TAGS:
            self._italic += 1
        elif tag in _UNDERLINE_TAGS:
            self._underline += 1
        elif tag in _STRIKE_TAGS:
            self._strike += 1

    def handle_startendtag(self, tag: str, attrs) -> None:  # noqa: ANN001
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            return
        if tag == "br":
            self._append_break()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag in _BOLD_TAGS:
            self._bold = max(0, self._bold - 1)
        elif tag in _ITALIC_TAGS:
            self._italic = max(0, self._italic - 1)
        elif tag in _UNDERLINE_TAGS:
            self._underline = max(0, self._underline - 1)
        elif tag in _STRIKE_TAGS:
            self._strike = max(0, self._strike - 1)
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        self._append_text(data)

    def close(self) -> None:  # noqa: D102
        super().close()
        self._flush()


def html_to_blocks(html: str) -> list[dict]:
    """把公告正文 HTML 转成 ``[{"runs": [...]}, ...]``。

    Args:
        html: 接口给的 ``msg.sContent`` 原文。

    Returns:
        段落列表；每段的 ``runs`` 里是行内片段，``{"br": True}`` 表示换行。
    """
    if not html:
        return []
    parser = _BodyParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - 解析失败就按纯文本兜底
        text = re.sub(r"<[^>]+>", " ", html)
        text = _NBSP.sub(" ", text).strip()
        return [{"runs": [{"t": text, "b": False, "i": False, "u": False, "s": False}]}] if text else []
    # 只剩空白的段落（<p>&nbsp;</p> 之类）不留，排版时会多出空行
    return [b for b in parser.blocks if not _blank_block(b)]


def _blank_block(block: dict) -> bool:
    """判断一个段落是否只有空白。"""
    for run in block.get("runs", []):
        if run.get("br"):
            continue
        if str(run.get("t") or "").strip():
            return False
    return True


def html_to_text(html: str) -> str:
    """把公告正文 HTML 压成纯文本（摘要、面板展示用）。"""
    blocks = html_to_blocks(html)
    out: list[str] = []
    for block in blocks:
        parts: list[str] = []
        for run in block.get("runs", []):
            if run.get("br"):
                parts.append("\n")
            else:
                parts.append(run.get("t", ""))
        line = "".join(parts).strip()
        if line:
            out.append(line)
    return "\n".join(out)
