# -*- coding: utf-8 -*-
"""重新生成 README 里用的预览图。

* ``docs/images/news-longimage-preview.jpg`` —— 公告长图
* ``docs/images/news-card-preview.jpg``     —— 公告卡片

长图和卡片都走本地 Typst 排版（和插件运行时同一套模板）。
拿不到线上公告时用内置样例，保证这条命令随时能跑。
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bpnews import api  # noqa: E402
from bpnews.typst import render as typst_render  # noqa: E402

OUT_DIR = ROOT / "docs" / "images"

SAMPLE = {
    "news_id": "2026111201",
    "title": "11月12日例行维护公告",
    "tag": "公告",
    "time": "2026-11-12 11:02:25",
    "url": "https://gm.qq.com/web202503/news-detail.html?newsid=2026111201",
    "cover": "",
    "content": (
        "<p>冒险者，您好：</p>"
        "<p>为配合例行维护，本服务器将于 <b>11 月 12 日 8:00 至 11:00</b> 进行例行维护，"
        "本次维护预计停服 180 分钟。维护期间，冒险者将无法登录游戏，请合理安排游戏时间。</p>"
        "<p>维护结束后，如出现异常，请尝试重新登录游戏或重启客户端。</p>"
        "<p>本次维护给各位冒险者带来的不便，敬请谅解。</p>"
    ),
}

SUMMARY = "为配合例行维护，本服务器将于 11 月 12 日 8:00 至 11:00 进行例行维护，预计停服 180 分钟。"


async def _latest() -> dict:
    """尽量拿一条真实公告；网络不通就用样例。"""
    try:
        items, _ = await api.fetch_list(page=1, page_size=5, tag_id=api.TAG_ALL)
        for item in items:
            detail = await api.fetch_detail(item.get("news_id"))
            if detail and detail.get("title"):
                return detail
    except Exception as exc:  # noqa: BLE001
        print(f"拉取线上公告失败，改用内置样例：{exc}")
    return dict(SAMPLE)


async def _main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    detail = await _latest()
    print(f"用公告：{detail.get('title')}")

    # 字体和素材缓存放在临时目录里，别把插件目录弄脏
    cache = Path(tempfile.mkdtemp(prefix="bp-preview-"))
    try:
        long_path, _ = await typst_render.render_long_image(detail, cache, max_height=0)
        long_out = OUT_DIR / "news-longimage-preview.jpg"
        long_out.write_bytes(long_path.read_bytes())
        print(f"长图 → {long_out.relative_to(ROOT)} ({long_out.stat().st_size} B)")

        card_path = await typst_render.render_card(detail, SUMMARY, cache)
        card_out = OUT_DIR / "news-card-preview.jpg"
        card_out.write_bytes(card_path.read_bytes())
        print(f"卡片 → {card_out.relative_to(ROOT)} ({card_out.stat().st_size} B)")
    finally:
        shutil.rmtree(cache, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
