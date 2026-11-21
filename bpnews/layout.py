# -*- coding: utf-8 -*-
"""公告长图的版式参数。

Typst 排版（``bpnews/typst``）和 Playwright 兜底（``bpnews/render.py`` +
``templates/article.html``）两条路共用这一份几何/主题/排版定义，避免同一个
公告在两条路上长得不一样。

约定：所有尺寸单位都是 **CSS 像素**（和浏览器一致），Typst 侧再按导出密度
换算成 pt。
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 默认值
# ---------------------------------------------------------------------------

# 画布宽度：默认取常见浏览器宽度
DEFAULT_WIDTH = 1280
# 正文栏宽度
DEFAULT_BODY_WIDTH = 1258
# 正文栏左右两侧的边框留白
DEFAULT_BORDER = 11
# 主题
DEFAULT_THEME = "dark"
# 段间距（px）
DEFAULT_PARA_SPACING = 14
# 行高（倍数）
DEFAULT_LINE_HEIGHT = 1.8
# 模块间距（px）：模块标题上方的留白
DEFAULT_MODULE_SPACING = 34

THEMES = ("dark", "light")

# ---------------------------------------------------------------------------
# 配色（深色 / 浅色）
# ---------------------------------------------------------------------------

THEME_COLORS: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#0F1218",
        "text": "#ECEDF2",
        "body": "#E4E6EC",
        "muted": "#A8ACB8",
        "dim": "#8A8E9C",
        "gold": "#FFD76E",
        "link": "#9CC0F5",
        "line": "#2A3040",
        "chip": "#2C281B",
        "panel": "#11151F",
        "kv_text": "#E6E9F0",
        "accent": "#4FC3F7",
    },
    "light": {
        "bg": "#FFFFFF",
        "text": "#1B1F27",
        "body": "#34383F",
        "muted": "#6E7480",
        "dim": "#98A0AE",
        "gold": "#A87418",
        "link": "#2C6BBF",
        "line": "#E3E6EC",
        "chip": "#FBF3E2",
        "panel": "#F4F6F9",
        "kv_text": "#FFFFFF",
        "accent": "#1D7FD1",
    },
}

# ---------------------------------------------------------------------------
# 版式细节：随画布宽度按比例缩放，但锁在舒服的区间里
# ---------------------------------------------------------------------------

_TYPE_RATIO: dict[str, float] = {
    "banner": 260 / 1280,
    "pad_top": 30 / 1280,
    "font_tag": 14 / 1280,
    "font_title": 30 / 1280,
    "font_meta": 15 / 1280,
    "font_body": 17 / 1280,
    "font_h2": 24 / 1280,
    "font_h3": 20 / 1280,
    "font_link": 14 / 1280,
    "font_foot": 13 / 1280,
}

_TYPE_LIMITS: dict[str, tuple[float, float]] = {
    "banner": (120.0, 420.0),
    "pad_top": (12.0, 60.0),
    "font_tag": (11.0, 18.0),
    "font_title": (20.0, 44.0),
    "font_meta": (12.0, 20.0),
    "font_body": (13.0, 24.0),
    "font_h2": (17.0, 32.0),
    "font_h3": (15.0, 28.0),
    "font_link": (11.0, 18.0),
    "font_foot": (10.0, 16.0),
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _to_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _to_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def resolve(
    *,
    width: Any = None,
    body_width: Any = None,
    border: Any = None,
    theme: Any = None,
    para_spacing: Any = None,
    line_height: Any = None,
    module_spacing: Any = None,
) -> dict[str, Any]:
    """算出一份完整的版式表。

    Returns:
        ``{"width", "body", "border", "theme", "colors", "para_spacing",
        "line_height", "module_spacing", "type": {...}}``，尺寸单位都是 px。
    """
    canvas = int(_clamp(_to_int(width, DEFAULT_WIDTH), 320, 4096))
    gap = int(_clamp(_to_int(border, DEFAULT_BORDER), 0, 200))
    body = _to_int(body_width, DEFAULT_BODY_WIDTH)
    if body <= 0:
        body = canvas - 2 * gap
    body = int(_clamp(body, 200, max(200, canvas - gap)))
    if body + 2 * gap > canvas:
        gap = max(0, (canvas - body) // 2)

    name = str(theme or "").strip().lower()
    if name not in THEMES:
        name = DEFAULT_THEME

    type_scale: dict[str, float] = {}
    for key, ratio in _TYPE_RATIO.items():
        low, high = _TYPE_LIMITS[key]
        type_scale[key] = round(_clamp(canvas * ratio, low, high), 2)

    return {
        "width": canvas,
        "body": body,
        "border": gap,
        "theme": name,
        "colors": dict(THEME_COLORS[name]),
        "para_spacing": round(_clamp(_to_float(para_spacing, DEFAULT_PARA_SPACING), 0, 120), 2),
        "line_height": round(_clamp(_to_float(line_height, DEFAULT_LINE_HEIGHT), 1.0, 3.0), 3),
        "module_spacing": round(
            _clamp(_to_float(module_spacing, DEFAULT_MODULE_SPACING), 0, 200), 2
        ),
        "type": type_scale,
    }


def fingerprint(layout: dict[str, Any]) -> str:
    """版式指纹：改了版式就该重新出图，不能吃旧缓存。"""
    parts = [
        f"w={layout['width']}",
        f"b={layout['body']}",
        f"g={layout['border']}",
        f"t={layout['theme']}",
        f"p={layout['para_spacing']}",
        f"l={layout['line_height']}",
        f"m={layout['module_spacing']}",
    ]
    parts += [f"{k}={v}" for k, v in sorted(layout["type"].items())]
    return "-".join(parts)


# ---------------------------------------------------------------------------
# 模块间距
# ---------------------------------------------------------------------------

# 各类块「上方留白」占的比例（模块标题按 module_spacing 算，其余按 para_spacing）。
GAP_BEFORE: dict[str, float] = {
    "p": 0.0,
    "img": 0.8,
    "h1": 1.0,
    "h2": 1.0,
    "h3": 0.7,
    "h4": 0.7,
}
# 各类块「下方留白」占段间距的比例。
GAP_AFTER: dict[str, float] = {
    "p": 1.0,
    "img": 0.8,
    "h1": 1.0,
    "h2": 1.0,
    "h3": 0.85,
    "h4": 0.85,
}
# 模块标题用模块间距做基准，其余用段间距。
_HEADING_KINDS = ("h1", "h2", "h3", "h4")


def block_gaps(
    kinds: list[str],
    *,
    para_spacing: float = DEFAULT_PARA_SPACING,
    module_spacing: float = DEFAULT_MODULE_SPACING,
) -> list[float]:
    """算每一块「上方留白」（px）。

    相邻两块之间取「前一块的下方留白」和「后一块的上方留白」里较大的一个 ——
    和 CSS 的外边距合并行为一致，所以 Typst 与网页两条路能长得一模一样。
    """
    para = float(para_spacing)
    module = float(module_spacing)

    def before(kind: str) -> float:
        ratio = GAP_BEFORE.get(kind, 0.0)
        base = module if kind in _HEADING_KINDS else para
        return round(base * ratio, 2)

    def after(kind: str) -> float:
        return round(para * GAP_AFTER.get(kind, 1.0), 2)

    gaps: list[float] = []
    previous: str | None = None
    for kind in kinds:
        top = before(kind)
        if previous is not None:
            top = max(top, after(previous))
        gaps.append(top)
        previous = kind
    return gaps


def apply_gaps(
    blocks: list[dict[str, Any]],
    *,
    para_spacing: float = DEFAULT_PARA_SPACING,
    module_spacing: float = DEFAULT_MODULE_SPACING,
) -> list[dict[str, Any]]:
    """给每个排版块补上 ``gap``（上方留白，px）。"""
    kinds = [str(block.get("kind") or "p") for block in blocks]
    gaps = block_gaps(
        kinds, para_spacing=para_spacing, module_spacing=module_spacing
    )
    for block, gap in zip(blocks, gaps):
        block["gap"] = gap
    return blocks
