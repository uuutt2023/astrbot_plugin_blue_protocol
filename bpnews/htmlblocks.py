# -*- coding: utf-8 -*-
"""公告正文 HTML → 结构化区块。

Typst 长图和 HTML 兜底长图共用这一份解析结果，保证两条路排出来的长图
一模一样。

**为什么要分块**：公告正文的「模块」在 HTML 里有三种形态，不认出来的话，
模块标题会和正文长得一模一样，模块之间也没有间距，读起来就是一堵墙：

1. 显式标题标签 ``<h1>``-``<h6>``（新闻、活动类公告常见）；
2. 整行加粗的 ``<strong>`` 行（「修复内容」「扭蛋活动、臻享卡商店相关更新」）；
3. 靠 ``<br/>`` 分行的短标题行（「以下为本次更新内容详情：」「1. 扭蛋活动轮换」）。

块的结构：

* ``{"kind": "h1"|"h2"|"h3"|"h4"|"p", "runs": [...]}``
* ``{"kind": "img", "src": "https://...", "alt": "..."}``

行内片段（run）：

* ``{"t": 文本, "b": 粗, "i": 斜, "u": 下划线, "s": 删除线, "href": 链接}``
* ``{"br": True}`` 表示换行
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
# 标题标签 → 块类型（h5/h6 没有单独的排版规格，并到 h4）
_HEADING_KINDS = {
    "h1": "h1", "h2": "h2", "h3": "h3", "h4": "h4", "h5": "h4", "h6": "h4",
}
_BOLD_TAGS = {"b", "strong"}
_ITALIC_TAGS = {"i", "em"}
_UNDERLINE_TAGS = {"u", "ins"}
_STRIKE_TAGS = {"s", "del", "strike"}
# 这些标签的内容直接丢掉（正文里不该出现）
_SKIP_TAGS = {"script", "style", "head", "title", "noscript", "iframe"}

# 标题识别的阈值
MAX_TITLE_LEN = 24      # 超过这个长度一定不是标题
MAX_SHORT_LEN = 16      # 「短行」的长度上限

# 编号式小标题：1. / 1、 / 1） / 一、 / （1）
_NUMBERED = re.compile(
    r"^(?:\d{1,2}\s*[.、)）]|[一二三四五六七八九十]{1,3}\s*[、.．]|[（(]\s*\d{1,2}\s*[)）])"
)
# 行尾是这些标点 → 是句子的结尾，不是标题
_SENTENCE_END = ("。", "！", "？", "!", "?", "；", ";", "，", ",", "、")
# 行尾是冒号 → 多半是「下面讲什么」的引导标题
_LABEL_END = ("：", ":")
# 实体里的不换行空格，统一成普通空格
_NBSP = re.compile("\xa0")
# 协议相对地址（//static.gametalk.qq.com/...）
_PROTOCOL_RELATIVE = re.compile(r"^//")


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------


class _BodyParser(HTMLParser):
    """把公告正文 HTML 拆成「块」和「图片」，保留顺序。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict] = []
        self._runs: list[dict] = []
        self._tag = "p"
        self._bold = 0
        self._italic = 0
        self._underline = 0
        self._strike = 0
        self._href = ""
        self._skip = 0

    # -- 内部 -------------------------------------------------------------

    def _flush(self) -> None:
        """把当前段落收尾，空段落丢掉。"""
        if self._runs:
            runs = _trim_runs(self._runs)
            if any(not r.get("br") and r.get("t") for r in runs):
                self.items.append(
                    {"type": "block", "tag": self._tag, "runs": runs}
                )
        self._runs = []
        self._tag = "p"

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
        href = self._href
        if self._runs:
            last = self._runs[-1]
            if (
                not last.get("br")
                and last.get("b", False) == bold
                and last.get("i", False) == italic
                and last.get("u", False) == underline
                and last.get("s", False) == strike
                and last.get("href", "") == href
            ):
                last["t"] += text
                return
        self._runs.append(
            {
                "t": text,
                "b": bold,
                "i": italic,
                "u": underline,
                "s": strike,
                "href": href,
            }
        )

    def _append_break(self) -> None:
        if self._skip:
            return
        if self._runs and not self._runs[-1].get("br"):
            self._runs.append({"br": True})

    def _append_image(self, src: str, alt: str) -> None:
        if self._skip or not src:
            return
        # 图片前后若有文字，先把文字收成一个段落，图片单独成块
        self._flush()
        self.items.append(
            {"type": "img", "src": _normalize_src(src), "alt": alt.strip()}
        )

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
        if tag == "img":
            values = {k.lower(): (v or "") for k, v in attrs}
            self._append_image(values.get("src", ""), values.get("alt", ""))
            return
        if tag == "a":
            self._href = ""
            for key, value in attrs:
                if (key or "").lower() == "href":
                    self._href = value or ""
            return
        if tag in _BLOCK_TAGS:
            self._flush()
            self._tag = tag
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
        if self._skip:
            return
        if tag == "br":
            self._append_break()
        elif tag == "img":
            values = {k.lower(): (v or "") for k, v in attrs}
            self._append_image(values.get("src", ""), values.get("alt", ""))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag == "a":
            self._href = ""
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


def _trim_runs(runs: list[dict]) -> list[dict]:
    """去掉首尾的换行和纯空白片段。"""
    out = list(runs)
    while out and (out[0].get("br") or not out[0].get("t", "").strip()):
        out.pop(0)
    while out and (out[-1].get("br") or not out[-1].get("t", "").strip()):
        out.pop()
    return out


def _normalize_src(src: str) -> str:
    """图片地址补上协议头。"""
    src = (src or "").strip()
    if _PROTOCOL_RELATIVE.match(src):
        return "https:" + src
    return src


# ---------------------------------------------------------------------------
# 标题识别
# ---------------------------------------------------------------------------


def _split_lines(runs: list[dict]) -> list[list[dict]]:
    """按换行把片段拆成若干行。"""
    lines: list[list[dict]] = [[]]
    for run in runs:
        if run.get("br"):
            lines.append([])
        else:
            lines[-1].append(run)
    return lines


def _line_text(line: list[dict]) -> str:
    return "".join(r.get("t", "") for r in line if not r.get("br"))


def _line_all_bold(line: list[dict]) -> bool:
    """整行是否都是加粗（`<strong>` 包住的一整行）。"""
    texts = [r for r in line if r.get("t")]
    return bool(texts) and all(r.get("b") for r in texts)


def _classify_lines(lines: list[list[dict]]) -> list[str | None]:
    """判断每一行是标题（h2/h3）还是正文。

    判定顺序（先排除，后认定）：

    1. 空行 / 太长 / 以句末标点结尾 → 正文；
    2. 整行加粗 → 标题（带编号的是小标题）；
    3. 以冒号结尾 → 标题；
    4. 编号开头（``1.`` / ``一、``）→ 小标题；
    5. 短行且下一行明显更长 → 标题。
    """
    kinds: list[str | None] = []
    for index, line in enumerate(lines):
        text = _line_text(line).strip()
        following = (
            _line_text(lines[index + 1]).strip()
            if index + 1 < len(lines)
            else ""
        )
        if not text or len(text) > MAX_TITLE_LEN:
            kinds.append(None)
        elif text[-1] in _SENTENCE_END:
            kinds.append(None)
        elif _line_all_bold(line):
            kinds.append("h3" if _NUMBERED.match(text) else "h2")
        elif text[-1] in _LABEL_END:
            kinds.append("h2")
        elif _NUMBERED.match(text):
            kinds.append("h3")
        elif len(text) <= MAX_SHORT_LEN and following:
            kinds.append("h2" if len(following) >= 2 * len(text) else None)
        else:
            kinds.append(None)

    # 第二轮：短行、且下一行是标题 → 自己也是上一级标题
    for index, line in enumerate(lines):
        if kinds[index] is not None:
            continue
        text = _line_text(line).strip()
        if not text or len(text) > MAX_SHORT_LEN:
            continue
        # 以句末标点结尾的是句子，再短也不是标题
        if text[-1] in _SENTENCE_END:
            continue
        if index + 1 < len(lines) and kinds[index + 1] is not None:
            kinds[index] = "h2"
    return kinds


def _join_lines(lines: list[list[dict]]) -> list[dict]:
    """把若干行接回一个片段列表（行与行之间是换行）。"""
    out: list[dict] = []
    for index, line in enumerate(lines):
        if index:
            out.append({"br": True})
        out.extend(line)
    return _trim_runs(out)


def _split_block(tag: str, runs: list[dict]) -> list[dict]:
    """把一个 HTML 块切成若干排版块（标题与正文分开）。"""
    if tag in _HEADING_KINDS:
        return [{"kind": _HEADING_KINDS[tag], "runs": runs}]

    lines = _split_lines(runs)
    kinds = _classify_lines(lines)
    if not any(kinds):
        return [{"kind": "p", "runs": runs}]

    out: list[dict] = []
    buffer: list[list[dict]] = []
    for line, kind in zip(lines, kinds):
        if kind is None:
            buffer.append(line)
            continue
        if buffer:
            segment = _join_lines(buffer)
            if segment:
                out.append({"kind": "p", "runs": segment})
            buffer = []
        out.append({"kind": kind, "runs": _join_lines([line])})
    if buffer:
        segment = _join_lines(buffer)
        if segment:
            out.append({"kind": "p", "runs": segment})
    return out


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------


def classify(html: str) -> list[dict]:
    """把公告正文 HTML 转成排版块列表。

    Args:
        html: 接口给的 ``sContent`` 原文。

    Returns:
        块的列表，每块是 ``{"kind": ..., "runs": [...]}`` 或
        ``{"kind": "img", "src": ..., "alt": ...}``。
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
        if not text:
            return []
        return [
            {
                "kind": "p",
                "runs": [
                    {"t": text, "b": False, "i": False, "u": False, "s": False,
                     "href": ""}
                ],
            }
        ]

    blocks: list[dict] = []
    for item in parser.items:
        if item["type"] == "img":
            blocks.append(
                {"kind": "img", "src": item["src"], "alt": item.get("alt", "")}
            )
            continue
        blocks.extend(_split_block(item["tag"], item["runs"]))
    return blocks


def to_text(blocks: list[dict]) -> str:
    """排版块 → 纯文本（摘要、面板展示用）。"""
    out: list[str] = []
    for block in blocks:
        if block.get("kind") == "img":
            continue
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


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def to_html(blocks: list[dict]) -> str:
    """排版块 → HTML（Playwright 兜底路径用，和 Typst 走同一份结构）。

    每块的上方留白用内联 ``margin-top`` 写死 —— 数值由
    :func:`bpnews.layout.apply_gaps` 算好，和 Typst 长图用的是同一份，
    所以两条路排出来的长图不会差出间距。
    """
    out: list[str] = []
    for block in blocks:
        kind = block.get("kind", "p")
        gap = block.get("gap")
        style = ""
        if gap is not None:
            style = f' style="margin:{float(gap)}px 0 0"'
        if kind == "img":
            src = _escape(str(block.get("src") or ""))
            alt = _escape(str(block.get("alt") or ""))
            if src:
                out.append(
                    f'<p class="img"{style}><img src="{src}" alt="{alt}"></p>'
                )
            continue
        inner: list[str] = []
        for run in block.get("runs", []):
            if run.get("br"):
                inner.append("<br>")
                continue
            text = _escape(str(run.get("t") or ""))
            if not text:
                continue
            if run.get("b"):
                text = f"<strong>{text}</strong>"
            if run.get("i"):
                text = f"<em>{text}</em>"
            if run.get("u"):
                text = f"<u>{text}</u>"
            if run.get("s"):
                text = f"<s>{text}</s>"
            href = str(run.get("href") or "")
            if href:
                text = f'<a href="{_escape(href)}">{text}</a>'
            inner.append(text)
        body = "".join(inner)
        if not body:
            continue
        tag = kind if kind in ("h1", "h2", "h3", "h4") else "p"
        out.append(f"<{tag}{style}>{body}</{tag}>")
    return "".join(out)
