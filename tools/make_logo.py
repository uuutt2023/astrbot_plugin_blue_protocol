# -*- coding: utf-8 -*-
"""生成插件图标 logo.png 与面板图标 blueprotocol-icon.png。

Blue Protocol: Star Resonance 公告插件的徽记：一颗四角星芒 + 共振波纹 + 星尘。
纯几何绘制，不依赖任何外部素材或网络。

    python tools/make_logo.py

输出：
    logo.png                        256×256（插件市场 / 管理面板图标）
    pages/blueprotocol-panel/blueprotocol-icon.png   128×128（面板首屏）
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SS = 4  # 超采样倍数，缩小后边缘更干净

BG_TOP = (34, 44, 72)
BG_BOTTOM = (15, 18, 24)
GOLD = (255, 215, 110)
GOLD_DEEP = (224, 163, 48)
GOLD_SOFT = (255, 236, 180)


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _background(size: int) -> Image.Image:
    """竖向渐变底 + 四角柔和光晕。"""
    img = Image.new("RGB", (size, size), BG_BOTTOM)
    draw = ImageDraw.Draw(img)
    for y in range(size):
        draw.line(
            [(0, y), (size, y)],
            fill=_lerp(BG_TOP, BG_BOTTOM, (y / max(1, size - 1)) ** 0.85),
        )
    glow = Image.new("L", (size, size), 0)
    gd = ImageDraw.Draw(glow)
    r = int(size * 0.52)
    gd.ellipse(
        [size // 2 - r, int(size * 0.30) - r, size // 2 + r, int(size * 0.30) + r],
        fill=110,
    )
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.16))
    img = Image.composite(Image.new("RGB", (size, size), (86, 108, 168)), img, glow)
    return img


def _sparkle(cx: float, cy: float, radius: float, points: int = 4) -> list:
    """四角星芒轮廓（外凸尖角 + 内凹弧边）。"""
    pts = []
    steps = 720
    for i in range(steps):
        th = 2 * math.pi * i / steps
        r = radius * (0.30 + 0.70 * abs(math.cos(points * th / 2)) ** 1.7)
        pts.append((cx + r * math.cos(th), cy + r * math.sin(th)))
    return pts


def _draw_logo(size: int, transparent: bool = False) -> Image.Image:
    img = (
        Image.new("RGBA", (size, size), (0, 0, 0, 0))
        if transparent
        else _background(size).convert("RGBA")
    )
    draw = ImageDraw.Draw(img)
    c = size / 2

    # 外圈细描边（徽章感）—— 透明底版本不画方框，只留徽记
    if not transparent:
        pad = int(size * 0.085)
        draw.rounded_rectangle(
            [pad, pad, size - pad, size - pad],
            radius=int(size * 0.20),
            outline=(255, 215, 110, 60),
            width=max(1, int(size * 0.006)),
        )

    # 共振波纹：两圈细弧
    for radius, width in ((size * 0.36, 0.010), (size * 0.42, 0.006)):
        bbox = [c - radius, c - radius, c + radius, c + radius]
        draw.arc(bbox, start=18, end=162, fill=(150, 175, 235), width=max(1, int(size * width)))
        draw.arc(bbox, start=198, end=342, fill=(150, 175, 235), width=max(1, int(size * width)))

    # 星尘
    for angle, dist, rad in (
        (24, 0.40, 0.009),
        (128, 0.43, 0.006),
        (212, 0.38, 0.007),
        (300, 0.44, 0.005),
        (76, 0.45, 0.005),
    ):
        th = math.radians(angle)
        px = c + dist * size * math.cos(th)
        py = c + dist * size * math.sin(th)
        rr = rad * size
        draw.ellipse([px - rr, py - rr, px + rr, py + rr], fill=GOLD_SOFT)

    # 主星芒：先画深金描边，再叠一层亮金渐变
    sparkle = _sparkle(c, c * 0.985, size * 0.335)
    draw.polygon(sparkle, fill=GOLD_DEEP)
    inner = _sparkle(c, c * 0.985, size * 0.295)
    draw.polygon(inner, fill=GOLD)

    # 星芒中心的宝石
    gem_r = size * 0.055
    draw.ellipse(
        [c - gem_r, c * 0.985 - gem_r, c + gem_r, c * 0.985 + gem_r],
        fill=(255, 246, 224),
    )
    return img


def main() -> None:
    # 插件市场 / 管理面板：带底色的方形徽章
    big = _draw_logo(256 * SS).resize((256, 256), Image.LANCZOS)
    big.save(ROOT / "logo.png", format="PNG", optimize=True)

    # 面板首屏：透明底徽记，融进 hero 背景里
    icon = _draw_logo(128 * SS, transparent=True).resize((128, 128), Image.LANCZOS)
    icon_dir = ROOT / "pages" / "blueprotocol-panel"
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon.save(icon_dir / "blueprotocol-icon.png", format="PNG", optimize=True)

    print("logo.png ->", ROOT / "logo.png")
    print("blueprotocol-icon.png ->", icon_dir / "blueprotocol-icon.png")


if __name__ == "__main__":
    main()
