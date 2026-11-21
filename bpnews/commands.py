# -*- coding: utf-8 -*-
"""指令前缀的解析与归一。

插件主程序（main.py）和面板后端（bpnews/page.py）都要处理同一份前缀配置，
规则放在这里，避免两边解析不一致。
"""

from __future__ import annotations

import re
from typing import Any

# 默认前缀：bp / blue protocol（blueprotocol 连写也算同一个）
DEFAULT_PREFIXES = ("bp", "blue protocol")

# 逗号、中文逗号、分号、换行 —— 分隔多个前缀
_SPLIT = re.compile(r"[,，;；\n\r]+")
# 归一时要抹掉的空白
_SPACES = re.compile(r"\s+")


def normalize(text: Any) -> str:
    """前缀归一：去掉所有空白 + 转小写。

    所以 "blue protocol"、"blueprotocol"、"Blue Protocol" 是同一个前缀。
    """
    return _SPACES.sub("", str(text or "")).lower()


def parse(value: Any) -> list[str]:
    """把配置值整理成一份干净的前缀列表。

    字符串按逗号/分号/换行分隔（**不按空格**，一段里的空格属于前缀本身，
    所以 "blue protocol" 是一个前缀）；列表按元素逐个处理。

    Returns:
        去掉空项与重复项后的列表；一个都没填时返回空列表。
    """
    if value is None:
        return []
    if isinstance(value, str):
        parts = _SPLIT.split(value)
    elif isinstance(value, (list, tuple, set)):
        parts = []
        for item in value:
            parts.extend(_SPLIT.split(str(item)))
    else:
        return []
    out: list[str] = []
    for part in parts:
        text = part.strip()
        if text and text not in out:
            out.append(text)
    return out


def resolve(value: Any) -> list[str]:
    """实际生效的前缀列表；没配就退回默认。"""
    parsed = parse(value)
    return parsed or list(DEFAULT_PREFIXES)


def to_set(value: Any) -> set[str]:
    """实际生效的前缀集合（归一后比较）。"""
    return {normalize(item) for item in resolve(value)}
