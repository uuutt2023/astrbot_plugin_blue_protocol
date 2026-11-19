# -*- coding: utf-8 -*-
"""Typst 排版用到的位图缓存（官方 KV 横幅、公告封面图）。

Typst 的 ``image()`` 只能读本地文件，远程 URL 得先落到磁盘。这里把官方 KV
横幅和公告封面都缓存在插件 data 目录里，避免每次排版都重新下载。
"""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

# 官网主视觉 KV（横幅）——卡片底图与长图顶部都用它
KV_URL = "https://game.gtimg.cn/images/bpm/web202412/kv.jpg"
# 官网公告详情页的装饰分隔图
NEWS_BG_URL = "https://game.gtimg.cn/images/bpm/web202412/news-detail-bg.jpg"

MAX_IMAGE_BYTES = 24 * 1024 * 1024
_TIMEOUT = 45


def assets_dir(data_dir: Path) -> Path:
    """插件位图缓存目录。"""
    return data_dir / "typst" / "assets"


def _download(url: str, target: Path, referer: str | None = None) -> bool:
    """下载到临时文件再原子替换；失败返回 False。"""
    headers = {"User-Agent": "Mozilla/5.0"}
    if referer:
        headers["Referer"] = referer
    tmp = target.with_name(f".{target.name}.part")
    try:
        req = urllib.request.Request(url, headers=headers)  # noqa: S310
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
            data = resp.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES or len(data) < 1024:
            return False
        tmp.write_bytes(data)
        tmp.replace(target)
        return True
    except Exception:  # noqa: BLE001 - 网络问题不该让整条渲染失败
        tmp.unlink(missing_ok=True)
        return False


def _is_jpeg(path: Path) -> bool:
    """看文件头是不是 JPEG。"""
    try:
        with path.open("rb") as fh:
            return fh.read(3) == b"\xff\xd8\xff"
    except OSError:
        return False


def _normalize_jpeg(path: Path) -> bool:
    """把缓存图统一转成真正的 JPEG。

    官网的公告封面其实返回的是 PNG，却挂在 ``.jpg`` 名下 —— Typst 认扩展名，
    会用 JPEG 解码器去读 PNG 然后直接报错。这里用 Pillow 统一转一道。
    """
    if _is_jpeg(path):
        return True
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        with Image.open(path) as im:
            im.load()
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.save(path, format="JPEG", quality=92)
        return True
    except Exception:  # noqa: BLE001 - 解不开就当这张图不可用
        return False


def ensure_asset(data_dir: Path, url: str, name: str) -> Path | None:
    """确保某张图在缓存目录里，返回本地路径；拿不到返回 None。"""
    directory = assets_dir(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    if target.is_file() and target.stat().st_size > 1024:
        return target if _normalize_jpeg(target) else None
    if _download(url, target, referer="https://gm.qq.com/"):
        if _normalize_jpeg(target):
            return target
        target.unlink(missing_ok=True)
    return None


def ensure_kv(data_dir: Path) -> Path | None:
    """官方 KV 横幅。"""
    return ensure_asset(data_dir, KV_URL, "kv.jpg")


def ensure_news_bg(data_dir: Path) -> Path | None:
    """官网公告页的装饰分隔图。"""
    return ensure_asset(data_dir, NEWS_BG_URL, "news-detail-bg.jpg")


def fetch_cover(data_dir: Path, url: str) -> Path | None:
    """公告封面图；按 URL 哈希命名缓存。"""
    if not url:
        return None
    name = f"cover_{hashlib.md5(url.encode()).hexdigest()[:16]}.jpg"
    return ensure_asset(data_dir, url, name)


def usage_bytes(data_dir: Path) -> int:
    """缓存目录占用字节数。"""
    directory = assets_dir(data_dir)
    if not directory.is_dir():
        return 0
    return sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
