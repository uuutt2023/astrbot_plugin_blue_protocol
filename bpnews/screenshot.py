# -*- coding: utf-8 -*-
"""公告长图渲染：把公告正文渲染成整页长图。

和「截官网网页」不同，这里是**自己渲染**：《星痕共鸣》的公告正文由
``searchNews.php`` 接口直接给 HTML（``msg.sContent``），套进
``templates/article.html`` 后用 Playwright 按配置的画布宽度整页截图。
好处是内容完整、不依赖官网那个 JS 渲染的 SPA、也不会被活动页弹窗干扰。

浏览器组件由插件首次使用时自动后台下载（``playwright install chromium``，
约 150MB），无需用户手动安装系统软件，依赖已在 requirements.txt 声明。
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import time
from pathlib import Path

from astrbot.api import logger

VIEWPORT_W = 1280
VIEWPORT_H = 844
DEVICE_SCALE = 1

_USER_AGENT_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)
_USER_AGENT_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

MAX_HEIGHT = 5000  # 默认截断高度（CSS px），0 表示不截断
JPEG_QUALITY = 88
MAX_BYTES = 2_500_000  # 单图字节预算，超了自动降质/缩放，避免平台拒收

_data_dir: Path | None = None
_ready: bool | None = None
_install_started = False


def configure(data_dir: Path) -> None:
    """插件初始化时注入数据目录，截图缓存落在其下的 news_shots/。"""
    global _data_dir
    _data_dir = data_dir


def _shot_dir() -> Path:
    if _data_dir is None:
        raise RuntimeError("screenshot.configure() 未调用")
    d = _data_dir / "news_shots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _shot_paths(key: str) -> tuple[Path, Path]:
    """(完整图路径, 截断图路径)。用文件名区分，省掉额外的标记文件。"""
    h = hashlib.md5(str(key).encode()).hexdigest()
    d = _shot_dir()
    return d / f"{h}.jpg", d / f"{h}_t.jpg"


def clean_shots(max_keep: int = 20, max_age: int = 7 * 86400) -> None:
    """清理历史截图：最多保留最近 max_keep 张 + 7 天兜底。"""
    try:
        now = time.time()
        files = [f for f in _shot_dir().iterdir() if f.is_file()]
        if len(files) > max_keep:
            for f in sorted(files, key=lambda x: x.stat().st_mtime)[:-max_keep]:
                f.unlink(missing_ok=True)
        for f in _shot_dir().iterdir():
            if f.is_file() and now - f.stat().st_mtime > max_age:
                f.unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 浏览器组件可用性
# ---------------------------------------------------------------------------


async def _probe() -> bool:
    """探测 Playwright chromium 是否可用（结果缓存）。"""
    global _ready
    if _ready is not None:
        return _ready
    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        try:
            b = await pw.chromium.launch(args=["--no-sandbox"])
            await b.close()
            _ready = True
        except Exception as e:  # noqa: BLE001
            logger.warning("Playwright chromium 不可用: %s", e)
            _ready = False
        await pw.stop()
    except Exception as e:  # noqa: BLE001
        logger.warning("Playwright 未安装或不可用: %s", e)
        _ready = False
    return _ready


async def _run_install() -> None:
    """后台下载 Playwright chromium（约 150MB，一次性）。"""
    logger.info("开始自动下载 Playwright chromium 浏览器组件（约 150MB）…")
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "playwright",
        "install",
        "chromium",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    global _ready
    _ready = None  # 重新探测
    if await _probe():
        logger.info("Playwright chromium 下载完成，公告长图已可用")
    else:
        logger.error("Playwright chromium 下载失败，公告图回退为卡片模式")


def request_install() -> bool:
    """触发后台下载（幂等），返回是否已开始。"""
    global _install_started
    if _install_started:
        return False
    _install_started = True
    try:
        asyncio.get_running_loop().create_task(_run_install())
        return True
    except RuntimeError:
        _install_started = False
        return False


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------


def _shrink_to_budget(path: Path, max_bytes: int) -> None:
    """超出字节预算时先降质、再等比缩小，避免超长公告图被平台拒收。"""
    if max_bytes <= 0 or path.stat().st_size <= max_bytes:
        return
    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow 不可用，跳过压缩（当前 %d 字节）", path.stat().st_size)
        return
    with Image.open(path) as im:
        src = im.convert("RGB")
    for quality, scale in ((78, 1.0), (72, 0.75), (66, 0.5), (60, 0.35)):
        img = (
            src
            if scale == 1.0
            else src.resize(
                (max(1, int(src.width * scale)), max(1, int(src.height * scale))),
                Image.LANCZOS,
            )
        )
        img.save(path, format="JPEG", quality=quality, optimize=True)
        if path.stat().st_size <= max_bytes:
            return
    logger.warning("截图压缩后仍有 %d 字节", path.stat().st_size)


async def _page_size(page) -> tuple[int, int]:
    """页面真实宽高（CSS px）。

    高度取 body 的实际盒子高度而不是 documentElement 的 scrollHeight ——
    后者至少等于视口高度，画布比内容高时会多截一段空白。
    """
    box = await page.evaluate(
        "() => {const d=document.documentElement, b=document.body||{};"
        "const r=b.getBoundingClientRect();"
        "return [Math.max(d.scrollWidth, b.scrollWidth||0, Math.ceil(r.width||0)),"
        " Math.max(Math.ceil(r.height||0), b.scrollHeight||0)];}"
    )
    return int(box[0]), int(box[1])


async def _wait_images(page, timeout_ms: int = 6000) -> None:
    """等封面图等位图解码完（decode 失败也不阻塞截图）。"""
    try:
        await page.wait_for_function(
            "() => {const imgs=Array.from(document.images||[]);"
            "return imgs.every(i=>i.complete);}",
            timeout=timeout_ms,
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("等待图片加载超时（不影响截图）: %s", e)


async def shot_article(
    html: str,
    key: str,
    max_height: int = MAX_HEIGHT,
    quality: int = JPEG_QUALITY,
    max_bytes: int = MAX_BYTES,
    width: int = VIEWPORT_W,
) -> tuple[str, bool]:
    """把一段 HTML 渲染成整页长图，返回 (jpg 路径, 是否因过长被截断)。

    按 key（通常是公告 id）做文件缓存：同一条公告推多个群只渲染一次。
    浏览器组件未就绪时触发后台下载并抛 RuntimeError("DOWNLOADING")，
    调用方应回退卡片模式并提示稍后自动生效。
    """
    full, trunc = _shot_paths(key)
    for p, was_truncated in ((full, False), (trunc, True)):
        if p.exists() and p.stat().st_size > 0:
            return str(p), was_truncated
    if not await _probe():
        request_install()
        raise RuntimeError("DOWNLOADING")

    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = None
    try:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        viewport_w = max(320, int(width or VIEWPORT_W))
        mobile = viewport_w <= 600
        ctx = await browser.new_context(
            viewport={"width": viewport_w, "height": VIEWPORT_H},
            device_scale_factor=DEVICE_SCALE,
            user_agent=_USER_AGENT_MOBILE if mobile else _USER_AGENT_DESKTOP,
            is_mobile=mobile,
            has_touch=mobile,
            locale="zh-CN",
        )
        page = await ctx.new_page()
        await page.set_content(html, wait_until="domcontentloaded", timeout=30000)
        await _wait_images(page)
        await page.wait_for_timeout(400)  # 等字体与排版落定

        width, height = await _page_size(page)
        truncated = max_height > 0 and height > max_height
        out = trunc if truncated else full
        await page.screenshot(
            path=str(out),
            type="jpeg",
            quality=quality,
            full_page=True,
            clip={
                "x": 0,
                "y": 0,
                "width": width,
                "height": min(height, max_height) if max_height > 0 else height,
            },
        )
        if not out.exists() or out.stat().st_size == 0:
            raise RuntimeError("截图文件为空")
        _shrink_to_budget(out, max_bytes)
        (full if truncated else trunc).unlink(missing_ok=True)
        return str(out), truncated
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:  # noqa: BLE001
                pass
        await pw.stop()
