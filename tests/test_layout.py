# -*- coding: utf-8 -*-
"""长图版式与 HTML 兜底路径的单测。

    python tests/test_layout.py

覆盖：
* ``bpnews.layout`` 的几何/主题/段间距/行高解析与边界；
* ``bpnews.render.render_article`` 把同一份版式注入 CSS 变量；
* Playwright 兜底的视口宽度参数（真跑浏览器那部分在 test_typst_render.py）。
"""

from __future__ import annotations

import os
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class _Logger:
    def info(self, *a, **k):
        pass

    warning = error = debug = info


def _install_astrbot_stub():
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    api.logger = _Logger()
    astrbot.api = api
    sys.modules["astrbot"] = astrbot
    sys.modules["astrbot.api"] = api


_install_astrbot_stub()

from bpnews import layout, render, screenshot  # noqa: E402

DETAIL = {
    "news_id": "2026111201",
    "title": "11月12日例行维护公告",
    "tag": "公告",
    "time": "2026-11-12 11:02:25",
    "url": "https://gm.qq.com/web202503/news-detail.html?newsid=2026111201",
    "cover": "",
    "content": "<p>冒险者，您好！</p><p>例行维护说明。</p>",
}


def _root_vars(html: str) -> dict[str, str]:
    """取 :root 里的 CSS 变量（后出现的覆盖先出现的）。"""
    block = re.search(r":root\s*\{(.*?)\n\}", html, re.S)
    assert block, "模板里找不到 :root 块"
    out: dict[str, str] = {}
    for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block.group(1)):
        out[name] = value.strip()
    return out


class LayoutResolveTests(unittest.TestCase):
    """版式解析。"""

    def test_defaults(self):
        spec = layout.resolve()
        self.assertEqual(spec["width"], 1280)
        self.assertEqual(spec["body"], 1258)
        self.assertEqual(spec["border"], 11)
        self.assertEqual(spec["theme"], "dark")
        self.assertEqual(spec["para_spacing"], 14)
        self.assertEqual(spec["line_height"], 1.8)

    def test_body_auto(self):
        spec = layout.resolve(width=1000, body_width=0, border=20)
        self.assertEqual(spec["body"], 960)

    def test_body_clamped_to_canvas(self):
        spec = layout.resolve(width=800, body_width=5000, border=11)
        self.assertLessEqual(spec["body"], spec["width"])

    def test_theme_validation(self):
        self.assertEqual(layout.resolve(theme="nope")["theme"], "dark")
        self.assertEqual(layout.resolve(theme="light")["theme"], "light")

    def test_numeric_guards(self):
        spec = layout.resolve(width="abc", border=None, para_spacing="x", line_height="y")
        self.assertEqual(spec["width"], 1280)
        self.assertEqual(spec["border"], 11)
        self.assertEqual(spec["para_spacing"], 14)
        self.assertEqual(spec["line_height"], 1.8)

    def test_type_scale_present(self):
        spec = layout.resolve()
        for key in ("banner", "pad_top", "cover_h", "font_tag", "font_title",
                    "font_meta", "font_body", "font_link", "font_foot"):
            self.assertIn(key, spec["type"])
            self.assertGreater(spec["type"][key], 0)

    def test_fingerprint_differs(self):
        base = layout.fingerprint(layout.resolve())
        self.assertNotEqual(base, layout.fingerprint(layout.resolve(theme="light")))
        self.assertNotEqual(base, layout.fingerprint(layout.resolve(width=1600)))


class RenderArticleTests(unittest.TestCase):
    """HTML 兜底长图。"""

    def test_injects_geometry(self):
        html = render.render_article(DETAIL)
        variables = _root_vars(html)
        self.assertEqual(variables["--page-w"], "1280px")
        self.assertEqual(variables["--body-w"], "1258px")
        self.assertEqual(variables["--border"], "11px")
        self.assertEqual(variables["--para-gap"], "14px")
        self.assertEqual(variables["--line-height"], "1.8")

    def test_injects_typography(self):
        html = render.render_article(DETAIL)
        variables = _root_vars(html)
        self.assertEqual(variables["--font-body"], "17px")
        self.assertEqual(variables["--font-title"], "30px")

    def test_custom_geometry(self):
        html = render.render_article(
            DETAIL, width=1600, body_width=1500, border=50, para_spacing=30, line_height=2.2
        )
        variables = _root_vars(html)
        self.assertEqual(variables["--page-w"], "1600px")
        self.assertEqual(variables["--body-w"], "1500px")
        self.assertEqual(variables["--border"], "50px")
        self.assertEqual(variables["--para-gap"], "30px")
        self.assertEqual(variables["--line-height"], "2.2")

    def test_dark_theme_colors(self):
        html = render.render_article(DETAIL, theme="dark")
        variables = _root_vars(html)
        self.assertEqual(variables["--bg"], "#0F1218")
        self.assertEqual(variables["--text"], "#ECEDF2")

    def test_light_theme_overrides_dark_defaults(self):
        html = render.render_article(DETAIL, theme="light")
        variables = _root_vars(html)
        self.assertEqual(variables["--bg"], "#FFFFFF")
        self.assertEqual(variables["--text"], "#1B1F27")
        self.assertEqual(variables["--gold"], "#A87418")

    def test_content_is_escaped_safely(self):
        html = render.render_article({**DETAIL, "title": "<script>x</script>"})
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_no_placeholder_left(self):
        html = render.render_article(DETAIL)
        self.assertNotIn("{{", html)


class ScreenshotParamTests(unittest.TestCase):
    """Playwright 兜底的参数。"""

    def test_default_viewport_is_browser_width(self):
        self.assertEqual(screenshot.VIEWPORT_W, 1280)

    def test_shot_article_accepts_width(self):
        import inspect

        signature = inspect.signature(screenshot.shot_article)
        self.assertIn("width", signature.parameters)
        self.assertEqual(signature.parameters["width"].default, screenshot.VIEWPORT_W)

    def test_desktop_and_mobile_user_agents(self):
        self.assertIn("Chrome", screenshot._USER_AGENT_DESKTOP)
        self.assertIn("iPhone", screenshot._USER_AGENT_MOBILE)


if __name__ == "__main__":
    unittest.main()
