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
    data = _download_bytes(url, referer=referer)
    if data is None:
        return False
    tmp = target.with_name(f".{target.name}.part")
    try:
        tmp.write_bytes(data)
        tmp.replace(target)
        return True
    except OSError:
        tmp.unlink(missing_ok=True)
        return False


def _download_bytes(url: str, referer: str | None = None) -> bytes | None:
    """下载字节；失败返回 None。"""
    headers = {"User-Agent": "Mozilla/5.0"}
    if referer:
        headers["Referer"] = referer
    try:
        req = urllib.request.Request(url, headers=headers)  # noqa: S310
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
            data = resp.read(MAX_IMAGE_BYTES + 1)
    except Exception:  # noqa: BLE001 - 网络问题不该让整条渲染失败
        return None
    if len(data) > MAX_IMAGE_BYTES or len(data) < 1024:
        return None
    return data


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


# 图片魔数 → 扩展名。官网的图 URL 后缀基本可靠，但仍有「PNG 挂 .jpg 名」的情况，
# 所以按内容判定格式，别信扩展名。
_IMAGE_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"RIFF", ".webp"),
    (b"BM", ".bmp"),
)


def _sniff_ext(data: bytes) -> str:
    """按文件头判断图片格式。"""
    for magic, ext in _IMAGE_MAGIC:
        if data.startswith(magic):
            return ext
    return ""


def fetch_inline(data_dir: Path, url: str) -> Path | None:
    """公告正文里的插图。

    和封面不同，正文插图很多是带透明通道的 PNG，转成 JPEG 会糊掉透明区域，
    所以这里保留原始格式，只按内容判定扩展名（Typst 认扩展名）。
    """
    if not url:
        return None
    directory = assets_dir(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"body_{hashlib.md5(url.encode()).hexdigest()[:16]}"
    for cached in sorted(directory.glob(f"{stem}.*")):
        if cached.is_file() and cached.stat().st_size > 1024:
            return cached
    data = _download_bytes(url, referer="https://gm.qq.com/")
    if data is None:
        return None
    ext = _sniff_ext(data)
    if not ext:
        return None
    target = directory / f"{stem}{ext}"
    try:
        target.write_bytes(data)
    except OSError:
        return None
    return target


def image_size(path: Path) -> tuple[int, int] | None:
    """读图片尺寸；读不出来返回 None。"""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as im:
            return im.size
    except Exception:  # noqa: BLE001 - 解不开就当没有尺寸信息
        return None


def usage_bytes(data_dir: Path) -> int:
    """缓存目录占用字节数。"""
    directory = assets_dir(data_dir)
    if not directory.is_dir():
        return 0
    return sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
