# -*- coding: utf-8 -*-
"""用 Typst 本地排版公告长图与卡片。

排版方案参考 SXP-Simon/astrbot_plugin_qq_group_daily_analysis：
* 编译器（``typst`` PyPI 包，内置 Rust Typst）跑在**独立子进程**里，带超时回收；
* 正文与文案都通过 ``data.json`` 传进模板，模板不执行任何外部代码；
* 字体只从插件 data 目录和系统字体取，必要时按固定来源下载中文字体；
* 先矢量导出量真实画布，校验像素预算后再栅格化，超长图逐档回落密度。

相比原来的「HTML + Playwright 整页截图」，Typst 不依赖浏览器组件（省掉约
150MB 的 chromium），排版也由模板精确控制，长图高度随正文自动伸缩。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from .. import layout
from . import assets, fonts
from .html2typst import html_to_blocks

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "typst"
_WORKER = Path(__file__).resolve().parent / "worker.py"

DEFAULT_PPI = 144
DEFAULT_TIMEOUT = 60.0
MAX_BYTES = 2_500_000

# 版式默认值统一放在 bpnews.layout 里，Typst 与 HTML 两条路共用。
DEFAULT_LONG_WIDTH = layout.DEFAULT_WIDTH
DEFAULT_LONG_BODY_WIDTH = layout.DEFAULT_BODY_WIDTH
DEFAULT_LONG_BORDER = layout.DEFAULT_BORDER
DEFAULT_LONG_THEME = layout.DEFAULT_THEME
DEFAULT_PARA_SPACING = layout.DEFAULT_PARA_SPACING
DEFAULT_LINE_HEIGHT = layout.DEFAULT_LINE_HEIGHT


def long_style(
    *,
    width: int = DEFAULT_LONG_WIDTH,
    body_width: int = DEFAULT_LONG_BODY_WIDTH,
    border: int = DEFAULT_LONG_BORDER,
    theme: str = DEFAULT_LONG_THEME,
    para_spacing: float = DEFAULT_PARA_SPACING,
    line_height: float = DEFAULT_LINE_HEIGHT,
    ppi: int = DEFAULT_PPI,
) -> dict[str, Any]:
    """把像素级的版式配置算成模板要用的样式表。

    返回的 ``style`` 里尺寸单位是 px，``scale`` 是「1px 等于多少 pt」
    （= 72 / ppi），模板用 ``px(v) = v * scale * 1pt`` 换算。
    """
    spec = layout.resolve(
        width=width,
        body_width=body_width,
        border=border,
        theme=theme,
        para_spacing=para_spacing,
        line_height=line_height,
    )
    style: dict[str, Any] = {
        "scale": 72.0 / float(max(72, min(300, int(ppi or DEFAULT_PPI)))),
        "width": spec["width"],
        "body": spec["body"],
        "border": spec["border"],
        "leading": spec["line_height"],
        "spacing": spec["para_spacing"],
    }
    style.update(spec["type"])
    return style


class TypstRenderError(RuntimeError):
    """Typst 排版失败（字体缺失、模板出错、超时等）。"""


# ---------------------------------------------------------------------------
# 缓存路径
# ---------------------------------------------------------------------------


def _shot_dir(data_dir: Path) -> Path:
    d = data_dir / "news_shots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(data_dir: Path, key: str, truncated: bool = False) -> Path:
    """缓存图片路径（统一存 JPEG）。"""
    h = hashlib.md5(str(key).encode()).hexdigest()
    suffix = "_t" if truncated else ""
    return _shot_dir(data_dir) / f"typst_{h}{suffix}.jpg"


# ---------------------------------------------------------------------------
# 任务目录
# ---------------------------------------------------------------------------


def _write_job(
    data_dir: Path,
    template: str,
    data: dict[str, Any],
    job_files: dict[str, Path | bytes],
) -> Path:
    """组装一次编译用的任务目录。"""
    if not _TEMPLATE_DIR.is_dir():
        raise TypstRenderError(f"Typst 模板目录缺失：{_TEMPLATE_DIR}")
    job_dir = Path(tempfile.mkdtemp(prefix="bp_typst_"))
    for typ in _TEMPLATE_DIR.glob("*.typ"):
        shutil.copyfile(typ, job_dir / typ.name)
    # main.typ 就是模板本体：#import 只取引用，不会把模块内容排进页面。
    shutil.copyfile(_TEMPLATE_DIR / f"{template}.typ", job_dir / "main.typ")
    (job_dir / "data.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    for name, source in job_files.items():
        if source is None:
            continue
        target = job_dir / name
        if isinstance(source, bytes):
            target.write_bytes(source)
        else:
            shutil.copyfile(source, target)
    return job_dir


# ---------------------------------------------------------------------------
# 编译
# ---------------------------------------------------------------------------


async def _compile(
    job_dir: Path, ppi: int, timeout: float, font_config: dict
) -> int:
    """跑隔离编译进程，返回实际使用的导出密度。"""
    (job_dir / "typst.json").write_text(
        json.dumps(font_config, ensure_ascii=False), encoding="utf-8"
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        str(_WORKER),
        str(job_dir),
        "--ppi",
        str(ppi),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(timeout):
            _, stderr = await process.communicate()
    except TimeoutError as error:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await asyncio.gather(process.wait(), return_exceptions=True)
        raise TypstRenderError(f"Typst 排版超过 {timeout:.0f} 秒预算，已终止") from error
    if process.returncode:
        detail = (stderr or b"").decode("utf-8", errors="replace").strip()
        raise TypstRenderError(detail or f"Typst 编译进程退出码 {process.returncode}")
    output = job_dir / "report.png"
    if not output.is_file() or output.stat().st_size == 0:
        raise TypstRenderError("Typst 没有产出图片")
    return output.stat().st_size


def _to_jpeg(source: Path, target: Path, quality: int) -> Path:
    """PNG 转 JPEG（平台更友好、体积更小）。Pillow 不可用时原样保留 PNG。"""
    try:
        from PIL import Image
    except ImportError:
        return source
    with Image.open(source) as im:
        im.convert("RGB").save(target, format="JPEG", quality=quality, optimize=True)
    return target


def _shrink_to_budget(path: Path, max_bytes: int) -> None:
    """超出字节预算时降质/缩放。"""
    if max_bytes <= 0 or path.stat().st_size <= max_bytes:
        return
    try:
        from PIL import Image
    except ImportError:
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


def _truncate(path: Path, max_height: int) -> bool:
    """按最大高度裁剪；返回是否发生了裁剪。"""
    if max_height <= 0:
        return False
    try:
        from PIL import Image
    except ImportError:
        return False
    with Image.open(path) as im:
        if im.height <= max_height:
            return False
        src = im.convert("RGB")
    src.crop((0, 0, src.width, max_height)).save(path, format="JPEG", quality=88)
    return True


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------


async def render_long_image(
    detail: dict[str, Any],
    data_dir: Path,
    *,
    ppi: int = DEFAULT_PPI,
    timeout: float = DEFAULT_TIMEOUT,
    max_height: int = 5000,
    quality: int = 88,
    max_bytes: int = MAX_BYTES,
    font_url: str | None = None,
    width: int = DEFAULT_LONG_WIDTH,
    body_width: int = DEFAULT_LONG_BODY_WIDTH,
    border: int = DEFAULT_LONG_BORDER,
    theme: str = DEFAULT_LONG_THEME,
    para_spacing: float = DEFAULT_PARA_SPACING,
    line_height: float = DEFAULT_LINE_HEIGHT,
) -> tuple[Path, bool]:
    """用 Typst 排一张公告长图，返回 (图片路径, 是否被截断)。"""
    spec = layout.resolve(
        width=width,
        body_width=body_width,
        border=border,
        theme=theme,
        para_spacing=para_spacing,
        line_height=line_height,
    )
    style = long_style(
        width=spec["width"],
        body_width=spec["body"],
        border=spec["border"],
        theme=spec["theme"],
        para_spacing=spec["para_spacing"],
        line_height=spec["line_height"],
        ppi=ppi,
    )
    key = str(detail.get("news_id") or detail.get("url") or detail.get("title") or "")
    # 版式变了就该重新出图，样式指纹进缓存键
    key = f"{key}|{layout.fingerprint(spec)}"
    full = _cache_path(data_dir, key, truncated=False)
    trunc = _cache_path(data_dir, key, truncated=True)
    for path in (full, trunc):
        if path.is_file() and path.stat().st_size > 0:
            return path, path == trunc

    font_config = fonts.ensure_font_config(data_dir, font_url)
    if not font_config.get("has_cjk"):
        raise TypstRenderError("Typst 找不到中文字体，无法排版公告正文")

    content = str(detail.get("content") or "")
    data = {
        "title": str(detail.get("title") or ""),
        "tag": str(detail.get("tag") or "公告"),
        "time": str(detail.get("time") or ""),
        "url": str(detail.get("url") or ""),
        "cover": "",
        "kv": "",
        "font": font_config.get("family") or "",
        "theme": spec["theme"],
        "colors": spec["colors"],
        "style": style,
        "body": html_to_blocks(content),
    }

    job_files: dict[str, Path | bytes] = {}
    kv = assets.ensure_kv(data_dir)
    if kv is not None:
        job_files["kv.jpg"] = kv
        data["kv"] = "kv.jpg"
    cover = assets.fetch_cover(data_dir, str(detail.get("cover") or ""))
    if cover is not None:
        job_files["cover.jpg"] = cover
        data["cover"] = "cover.jpg"

    job_dir = _write_job(data_dir, "long_image", data, job_files)
    try:
        await _compile(job_dir, ppi, timeout, font_config)
        produced = job_dir / "report.png"
        staged = _shot_dir(data_dir) / f".staged_{full.stem}.jpg"
        converted = _to_jpeg(produced, staged, quality)
        truncated = _truncate(converted, max_height)
        _shrink_to_budget(converted, max_bytes)
        final = (trunc if truncated else full).with_suffix(".jpg")
        if converted != final:
            converted.replace(final)
        (full if truncated else trunc).with_suffix(".jpg").unlink(missing_ok=True)
        return final, truncated
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


async def render_card(
    item: dict[str, Any],
    summary: str,
    data_dir: Path,
    *,
    ppi: int = DEFAULT_PPI,
    timeout: float = DEFAULT_TIMEOUT,
    quality: int = 88,
    max_bytes: int = MAX_BYTES,
    font_url: str | None = None,
) -> Path:
    """用 Typst 排一张公告卡片，返回图片路径。"""
    key = "card:" + str(
        item.get("news_id") or item.get("url") or item.get("title") or ""
    )
    cached = _cache_path(data_dir, key, truncated=False).with_suffix(".jpg")
    if cached.is_file() and cached.stat().st_size > 0:
        return cached

    font_config = fonts.ensure_font_config(data_dir, font_url)
    if not font_config.get("has_cjk"):
        raise TypstRenderError("Typst 找不到中文字体，无法排版卡片")

    data = {
        "title": str(item.get("title") or ""),
        "tag": str(item.get("tag") or "公告"),
        "time": str(item.get("time") or ""),
        "url": str(item.get("url") or ""),
        "desc": str(summary or ""),
        "kv": "",
        "font": font_config.get("family") or "",
        "theme": "dark",
        "colors": dict(layout.THEME_COLORS["dark"]),
    }

    job_files: dict[str, Path | bytes] = {}
    kv = assets.ensure_kv(data_dir)
    if kv is not None:
        job_files["kv.jpg"] = kv
        data["kv"] = "kv.jpg"
    bg = assets.ensure_news_bg(data_dir)
    if bg is not None:
        job_files["news-detail-bg.jpg"] = bg

    job_dir = _write_job(data_dir, "card", data, job_files)
    try:
        await _compile(job_dir, ppi, timeout, font_config)
        produced = job_dir / "report.png"
        out = _to_jpeg(produced, cached, quality)
        _shrink_to_budget(out, max_bytes)
        return out
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def status(data_dir: Path) -> dict:
    """Typst 排版可用状态（面板展示用）。"""
    try:
        import typst  # noqa: F401

        available = True
    except ImportError:
        available = False
    summary = fonts.font_summary(data_dir)
    return {
        "available": available,
        "font_source": summary.get("source", "none"),
        "managed_fonts": summary.get("managed_count", 0),
        "system_cjk": summary.get("system_cjk", False),
    }


def font_status(data_dir: Path) -> dict:
    """面板展示用的 Typst 字体状态。"""
    return fonts.font_summary(data_dir)


def asset_usage(data_dir: Path) -> int:
    """Typst 位图缓存占用字节数。"""
    return assets.usage_bytes(data_dir)
