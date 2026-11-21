# -*- coding: utf-8 -*-
"""公告正文分块与模块版式（bpnews/htmlblocks.py + bpnews/layout.py）。

公告的「模块」在 HTML 里有三种形态，都得认出来，否则模块标题和正文长得
一模一样，模块之间也没有间距，读起来就是一堵墙：

1. 显式标题标签 ``<h1>``-``<h6>``；
2. 整行加粗的 ``<strong>`` 行；
3. 靠 ``<br/>`` 分行的短标题行。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bpnews import htmlblocks, layout  # noqa: E402


def kinds(blocks):
    return [block.get("kind") for block in blocks]


def text_of(block):
    return htmlblocks.to_text([block])


class ClassifyTests(unittest.TestCase):
    """正文 HTML → 排版块。"""

    def test_plain_paragraphs(self):
        blocks = htmlblocks.classify("<p>第一段</p><p>第二段</p>")
        self.assertEqual(kinds(blocks), ["p", "p"])
        self.assertEqual(blocks[0]["runs"][0]["t"], "第一段")

    def test_explicit_headings(self):
        blocks = htmlblocks.classify("<h2>大模块</h2><p>正文</p><h3>小模块</h3>")
        self.assertEqual(kinds(blocks), ["h2", "p", "h3"])

    def test_h5_h6_fold_into_h4(self):
        blocks = htmlblocks.classify("<h5>五级</h5><h6>六级</h6>")
        self.assertEqual(kinds(blocks), ["h4", "h4"])

    def test_bold_whole_line_is_a_module_title(self):
        html = "<p><strong>修复内容</strong><br />正文一段</p>"
        blocks = htmlblocks.classify(html)
        self.assertEqual(kinds(blocks), ["h2", "p"])
        self.assertEqual(text_of(blocks[0]), "修复内容")

    def test_numbered_bold_line_is_a_sub_title(self):
        html = "<p><strong>1. 扭蛋活动轮换</strong><br />正文</p>"
        blocks = htmlblocks.classify(html)
        self.assertEqual(kinds(blocks), ["h3", "p"])

    def test_label_line_ending_with_colon_is_a_title(self):
        html = "<p>前面的话。<br />以下为本次更新内容详情：<br />正文</p>"
        blocks = htmlblocks.classify(html)
        self.assertEqual(kinds(blocks), ["p", "h2", "p"])

    def test_numbered_plain_line_is_a_sub_title(self):
        html = "<p>1. 扭蛋活动轮换<br />当前时装扭蛋活动……</p>"
        blocks = htmlblocks.classify(html)
        self.assertEqual(kinds(blocks), ["h3", "p"])

    def test_short_line_before_a_longer_one_is_a_title(self):
        html = "<p>S4赛季群星名录开启<br />群星名录上榜时间：11月12日维护后至12月8日</p>"
        blocks = htmlblocks.classify(html)
        self.assertEqual(kinds(blocks), ["h2", "p"])

    def test_sentence_ending_lines_stay_body(self):
        html = "<p>冒险者，您好！<br />《星痕共鸣》已于11月12日进行例行维护。</p>"
        blocks = htmlblocks.classify(html)
        self.assertEqual(kinds(blocks), ["p"])

    def test_long_line_is_never_a_title(self):
        html = "<p>" + "长" * 40 + "<br />正文</p>"
        blocks = htmlblocks.classify(html)
        self.assertEqual(kinds(blocks), ["p"])

    def test_images_become_their_own_block(self):
        html = '<p><img src="//static.gametalk.qq.com/a.png" alt=""></p><p>正文</p>'
        blocks = htmlblocks.classify(html)
        self.assertEqual(kinds(blocks), ["img", "p"])
        self.assertEqual(blocks[0]["src"], "https://static.gametalk.qq.com/a.png")

    def test_image_alone_in_a_paragraph_is_not_lost(self):
        html = '<p>前文</p><p><img src="https://x/y.png"/></p><p>后文</p>'
        blocks = htmlblocks.classify(html)
        self.assertEqual(kinds(blocks), ["p", "img", "p"])

    def test_link_text_and_href_are_kept(self):
        blocks = htmlblocks.classify('<p><a href="https://gm.qq.com/x">点击查看</a></p>')
        run = blocks[0]["runs"][0]
        self.assertEqual(run["t"], "点击查看")
        self.assertEqual(run["href"], "https://gm.qq.com/x")

    def test_inline_colour_is_dropped(self):
        """正文里的 span 颜色（有时是黑色）不能带进深色主题。"""
        blocks = htmlblocks.classify('<p><span style="color:#000"><strong>标题</strong></span></p>')
        self.assertEqual(kinds(blocks), ["h2"])
        self.assertNotIn("color", str(blocks[0]))

    def test_blank_blocks_are_dropped(self):
        self.assertEqual(htmlblocks.classify("<p>&nbsp;</p><p>正文</p>"), htmlblocks.classify("<p>正文</p>"))

    def test_empty_input(self):
        self.assertEqual(htmlblocks.classify(""), [])

    def test_broken_html_falls_back_to_text(self):
        blocks = htmlblocks.classify("<p>没闭合的标签<div>")
        self.assertTrue(blocks)
        self.assertEqual(kinds(blocks)[0], "p")


class ToHtmlTests(unittest.TestCase):
    """排版块 → HTML（网页兜底路径）。"""

    def test_headings_become_heading_tags(self):
        blocks = htmlblocks.classify("<h2>大模块</h2><p>正文</p>")
        out = htmlblocks.to_html(blocks)
        self.assertIn("<h2>大模块</h2>", out)
        self.assertIn("<p>正文</p>", out)

    def test_gap_becomes_inline_margin(self):
        blocks = layout.apply_gaps(htmlblocks.classify("<p>正文</p>"))
        out = htmlblocks.to_html(blocks)
        self.assertIn("margin:", out)

    def test_escapes_text(self):
        blocks = htmlblocks.classify("<p>a &lt; b</p>")
        self.assertIn("&lt;", htmlblocks.to_html(blocks))

    def test_image_keeps_source(self):
        blocks = htmlblocks.classify('<p><img src="https://x/y.png"/></p>')
        out = htmlblocks.to_html(blocks)
        self.assertIn('src="https://x/y.png"', out)
        self.assertIn('class="img"', out)


class GapTests(unittest.TestCase):
    """模块间距：相邻两块之间取较大的那个留白。"""

    def test_paragraph_gap_uses_para_spacing(self):
        gaps = layout.block_gaps(["p", "p"], para_spacing=14, module_spacing=34)
        self.assertEqual(gaps, [0, 14])

    def test_module_heading_gets_the_module_spacing(self):
        gaps = layout.block_gaps(["p", "h2"], para_spacing=14, module_spacing=34)
        self.assertEqual(gaps[1], 34)

    def test_sub_heading_gets_less(self):
        gaps = layout.block_gaps(["p", "h3"], para_spacing=14, module_spacing=34)
        self.assertEqual(gaps[1], round(34 * 0.7, 2))

    def test_gap_after_a_heading_is_the_larger_of_the_two(self):
        """标题后接正文：留白 = max(标题下方, 正文上方)。"""
        gaps = layout.block_gaps(["h2", "p"], para_spacing=14, module_spacing=34)
        self.assertEqual(gaps[1], 14)

    def test_paragraph_then_heading_takes_the_module_spacing(self):
        gaps = layout.block_gaps(["p", "h2"], para_spacing=14, module_spacing=34)
        self.assertEqual(gaps[1], 34)

    def test_module_spacing_zero_flattens_headings(self):
        gaps = layout.block_gaps(["p", "h2"], para_spacing=14, module_spacing=0)
        self.assertEqual(gaps[1], 14)

    def test_apply_gaps_writes_the_field(self):
        blocks = layout.apply_gaps(
            htmlblocks.classify("<p>正文</p><h2>模块</h2>"),
            para_spacing=14,
            module_spacing=34,
        )
        self.assertEqual([b["gap"] for b in blocks], [0, 34])


class LayoutTests(unittest.TestCase):
    """版式表。"""

    def test_module_spacing_default(self):
        self.assertEqual(layout.resolve()["module_spacing"], 34)

    def test_module_spacing_is_configurable(self):
        self.assertEqual(
            layout.resolve(module_spacing=52)["module_spacing"], 52
        )

    def test_module_spacing_is_clamped(self):
        self.assertEqual(layout.resolve(module_spacing=9999)["module_spacing"], 200)
        self.assertEqual(layout.resolve(module_spacing=-5)["module_spacing"], 0)

    def test_heading_type_scale(self):
        spec = layout.resolve()
        self.assertGreater(spec["type"]["font_h2"], spec["type"]["font_body"])
        self.assertGreater(spec["type"]["font_h3"], spec["type"]["font_body"])

    def test_fingerprint_changes_with_module_spacing(self):
        a = layout.fingerprint(layout.resolve(module_spacing=34))
        b = layout.fingerprint(layout.resolve(module_spacing=50))
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
