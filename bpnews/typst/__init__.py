# -*- coding: utf-8 -*-
"""Typst 本地排版。

排版方案参考 SXP-Simon/astrbot_plugin_qq_group_daily_analysis：
编译器跑在独立子进程里（超时即回收），正文通过 JSON 交给模板，字体只从
插件 data 目录与系统字体取。

对外只暴露 :func:`render_long_image` 与 :func:`render_card`。
"""

from __future__ import annotations

from .render import (
    DEFAULT_PPI,
    DEFAULT_TIMEOUT,
    TypstRenderError,
    asset_usage,
    font_status,
    render_card,
    render_long_image,
)

__all__ = [
    "DEFAULT_PPI",
    "DEFAULT_TIMEOUT",
    "TypstRenderError",
    "asset_usage",
    "font_status",
    "render_card",
    "render_long_image",
]
