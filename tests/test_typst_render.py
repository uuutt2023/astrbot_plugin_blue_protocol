# -*- coding: utf-8 -*-
"""Typst 本地排版的测试。

排版方案参考 SXP-Simon/astrbot_plugin_qq_group_daily_analysis：
隔离编译进程、JSON 数据契约、字体解析与像素预算。

真机排版需要 ``typst`` 依赖与可用的中文字体，缺任一项就跳过那几条用例；
纯逻辑（HTML→Typst 结构、字体解析、模板契约）始终可跑。
"""

from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bpnews.typst import fonts, html2typst, render, worker  # noqa: E402
from bpnews.typst.render import TypstRenderError  # noqa: E402


def _typst_available() -> bool:
    try:
        import typst  # noqa: F401
    except ImportError:
        return False
    return True


def _cjk_available() -> bool:
    return bool(fonts.pick_cjk_family(fonts.system_families()))


SKIP_REASON = "需要 typst 依赖与中文字体"


class HtmlToBlocksTests(unittest.TestCase):
    """公告正文 HTML → Typst 结构。"""

    def test_paragraphs_split(self):
        blocks = html2typst.html_to_blocks("<p>第一段</p><p>第二段</p>")
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["runs"][0]["t"], "第一段")

    def test_bold_and_italic_flags(self):
        blocks = html2typst.html_to_blocks("<p>普通<b>粗体</b><i>斜体</i></p>")
        runs = blocks[0]["runs"]
        by_text = {r.get("t"): r for r in runs}
        self.assertFalse(by_text["普通"]["b"])
        self.assertTrue(by_text["粗体"]["b"])
        self.assertTrue(by_text["斜体"]["i"])

    def test_line_break_kept(self):
        blocks = html2typst.html_to_blocks("<p>第一行<br/>第二行</p>")
        runs = blocks[0]["runs"]
        self.assertTrue(any(r.get("br") for r in runs))
        self.assertEqual(runs[0]["t"], "第一行")

    def test_entities_decoded(self):
        blocks = html2typst.html_to_blocks("<p>&ldquo;引号&rdquo;&amp;&nbsp;&times;</p>")
        text = blocks[0]["runs"][0]["t"]
        self.assertIn("“", text)
        self.assertIn("&", text)
        self.assertIn("×", text)

    def test_nbsp_becomes_space(self):
        blocks = html2typst.html_to_blocks("<p>甲\xa0乙</p>")
        self.assertEqual(blocks[0]["runs"][0]["t"], "甲 乙")

    def test_script_and_style_dropped(self):
        blocks = html2typst.html_to_blocks(
            "<style>p{color:red}</style><script>alert(1)</script><p>正文</p>"
        )
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["runs"][0]["t"], "正文")

    def test_empty_html(self):
        self.assertEqual(html2typst.html_to_blocks(""), [])
        self.assertEqual(html2typst.html_to_blocks("   "), [])

    def test_text_helper(self):
        text = html2typst.html_to_text("<p>第一段</p><p>第二段<br/>换行</p>")
        self.assertIn("第一段", text)
        self.assertIn("\n", text)


class LayoutTests(unittest.TestCase):
    """版式参数（几何/主题/段间距/行高）。"""

    def test_defaults_match_browser_width(self):
        from bpnews import layout

        spec = layout.resolve()
        assert spec["width"] == 1280
        assert spec["body"] == 1258
        assert spec["border"] == 11
        assert spec["theme"] == "dark"
        assert spec["para_spacing"] == 14
        assert spec["line_height"] == 1.8

    def test_body_width_zero_follows_canvas(self):
        from bpnews import layout

        spec = layout.resolve(width=1000, body_width=0, border=20)
        assert spec["body"] == 1000 - 40

    def test_body_width_cannot_exceed_canvas(self):
        from bpnews import layout

        spec = layout.resolve(width=800, body_width=5000, border=11)
        assert spec["body"] <= spec["width"]
        assert spec["body"] + 2 * spec["border"] <= spec["width"] + 1

    def test_invalid_theme_falls_back(self):
        from bpnews import layout

        assert layout.resolve(theme="blue")["theme"] == "dark"
        assert layout.resolve(theme="LIGHT")["theme"] == "light"

    def test_out_of_range_values_are_clamped(self):
        from bpnews import layout

        spec = layout.resolve(width=10, border=-5, para_spacing=9999, line_height=99)
        assert spec["width"] >= 320
        assert spec["border"] >= 0
        assert spec["para_spacing"] <= 120
        assert spec["line_height"] <= 3.0

    def test_both_themes_have_full_palette(self):
        from bpnews import layout

        for theme in layout.THEMES:
            colors = layout.THEME_COLORS[theme]
            for key in ("bg", "text", "body", "muted", "dim", "gold", "link", "line",
                        "chip", "panel", "kv_text", "accent"):
                assert colors[key].startswith("#"), f"{theme}/{key}"
                assert len(colors[key]) == 7, f"{theme}/{key}"

    def test_fingerprint_changes_with_layout(self):
        from bpnews import layout

        a = layout.fingerprint(layout.resolve())
        b = layout.fingerprint(layout.resolve(theme="light"))
        c = layout.fingerprint(layout.resolve(width=1600))
        assert a != b and a != c and b != c

    def test_typst_style_converts_px_to_pt(self):
        style = render.long_style(width=1280, ppi=144)
        assert style["scale"] == 0.5
        assert style["width"] == 1280
        assert style["body"] == 1258
        assert style["border"] == 11
        assert style["leading"] == 1.8
        assert style["spacing"] == 14
        # 144 PPI 下 1px = 0.5pt，画布就是 640pt
        assert round(style["width"] * style["scale"], 3) == 640.0


class FontTests(unittest.TestCase):
    """字体解析。"""

    def test_resolve_returns_shape(self):
        state = fonts.resolve(Path("/tmp/bp-fonts-test"))
        for key in ("font_paths", "include_system_fonts", "has_cjk", "source"):
            self.assertIn(key, state)
        self.assertIn(state["source"], ("managed", "system", "none"))

    def test_pick_cjk_family(self):
        self.assertEqual(fonts.pick_cjk_family(["Inter", "Noto Sans CJK SC"]), "Noto Sans CJK SC")
        self.assertIsNone(fonts.pick_cjk_family(["Inter", "Roboto"]))

    def test_list_fonts_ignores_other_files(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.ttf").write_bytes(b"x")
            (d / "b.otf").write_bytes(b"x")
            (d / "c.txt").write_text("x")
            self.assertEqual(fonts.list_fonts(d), ["a.ttf", "b.otf"])


class TemplateContractTests(unittest.TestCase):
    """模板与数据契约。"""

    def test_template_files_exist(self):
        for name in ("common.typ", "long_image.typ", "card.typ"):
            self.assertTrue((ROOT / "templates" / "typst" / name).is_file(), name)

    def test_templates_read_data_json(self):
        for name in ("long_image.typ", "card.typ"):
            text = (ROOT / "templates" / "typst" / name).read_text(encoding="utf-8")
            self.assertIn('json("data.json")', text, name)

    def test_card_uses_official_kv_and_gradient(self):
        text = (ROOT / "templates" / "typst" / "card.typ").read_text(encoding="utf-8")
        self.assertIn('image(d.kv', text)
        self.assertIn("scrim(angle: 45deg)", text)
        self.assertIn("c.accent", text)

    def test_long_image_uses_kv_banner(self):
        text = (ROOT / "templates" / "typst" / "long_image.typ").read_text(encoding="utf-8")
        self.assertIn("kv_banner", text)
        self.assertIn("发布时间：", text)

    def test_worker_rejects_bad_ppi(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            (job / "main.typ").write_text('#set page(width: 10pt)\n', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                worker.compile_job(job, raster_ppi=1)


class TypstRenderTests(unittest.TestCase):
    """真机排版（需要 typst + 中文字体）。"""

    def setUp(self):
        if not _typst_available() or not _cjk_available():
            self.skipTest(SKIP_REASON)
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    @staticmethod
    def _detail():
        return {
            "news_id": "2026111201",
            "title": "11月12日例行维护公告",
            "tag": "公告",
            "time": "2026-11-12 11:02:25",
            "url": "https://gm.qq.com/web202503/news-detail.html?newsid=2026111201",
            "cover": "",
            "content": "<p>冒险者，您好！</p><p><b>例行维护</b>说明。</p><p>换行<br/>测试</p>",
        }

    def test_render_long_image(self):
        path, truncated = asyncio.run(
            render.render_long_image(self._detail(), self.data_dir, max_height=0)
        )
        self.assertTrue(path.is_file())
        self.assertGreater(path.stat().st_size, 0)
        self.assertFalse(truncated)
        from PIL import Image

        with Image.open(path) as im:
            self.assertEqual(im.width, 1280)

    def test_render_long_image_truncates(self):
        path, truncated = asyncio.run(
            render.render_long_image(self._detail(), self.data_dir, max_height=120)
        )
        self.assertTrue(truncated)
        from PIL import Image

        with Image.open(path) as im:
            self.assertEqual(im.height, 120)

    def test_render_card(self):
        path = asyncio.run(
            render.render_card(self._detail(), "摘要内容。", self.data_dir)
        )
        self.assertTrue(path.is_file())
        from PIL import Image

        with Image.open(path) as im:
            self.assertEqual(im.size, (800, 720))

    def test_render_uses_configured_width(self):
        """画布宽度、正文宽度、边框都按配置来。"""
        path, _ = asyncio.run(
            render.render_long_image(
                self._detail(),
                self.data_dir,
                max_height=0,
                width=1000,
                body_width=900,
                border=50,
            )
        )
        from PIL import Image

        with Image.open(path) as im:
            self.assertEqual(im.width, 1000)

    def test_light_theme_renders(self):
        path, _ = asyncio.run(
            render.render_long_image(self._detail(), self.data_dir, max_height=0, theme="light")
        )
        self.assertTrue(path.is_file())
        # 浅色主题：左上角应该是白底（深色主题是近黑）
        from PIL import Image

        with Image.open(path) as im:
            rgb = im.convert("RGB")
            self.assertGreater(sum(rgb.getpixel((5, im.height - 5))) / 3, 200)

    def test_theme_changes_cache_key(self):
        dark = asyncio.run(
            render.render_long_image(self._detail(), self.data_dir, max_height=0)
        )[0]
        light = asyncio.run(
            render.render_long_image(
                self._detail(), self.data_dir, max_height=0, theme="light"
            )
        )[0]
        self.assertNotEqual(dark, light)

    def test_render_is_cached(self):
        first = asyncio.run(
            render.render_long_image(self._detail(), self.data_dir, max_height=0)
        )[0]
        second = asyncio.run(
            render.render_long_image(self._detail(), self.data_dir, max_height=0)
        )[0]
        self.assertEqual(first, second)

    def test_status_shape(self):
        state = render.status(self.data_dir)
        self.assertIn("available", state)
        self.assertIn(state["font_source"], ("managed", "system", "none"))

    def test_worker_reports_missing_font(self):
        """没有中文字体时要明确报错，而不是渲染出空白图。"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            (job / "main.typ").write_text('#set page(width: 10pt)\n', encoding="utf-8")
            (job / "typst.json").write_text(
                json.dumps({"font_paths": [], "include_system_fonts": False}),
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError):
                worker.compile_job(job)


if __name__ == "__main__":
    unittest.main()
