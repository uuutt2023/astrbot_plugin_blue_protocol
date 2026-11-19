"""检查有没有漏掉 i18n 的英文文案，以及卡片 / 长图模板的样式约定。

覆盖：
* main.py 里所有发给聊天的文案必须是中文（help 指令是双语，单独校验）；
* 面板 <title> 必须走 i18n；
* 卡片 / 长图模板必须用官方 KV 底图，且不能残留英文标签；
* README 单语版本必须与双语 README 同步；
* metadata.yaml 的 readmes 映射必须指向真实存在的 Markdown。
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "pages" / "blueprotocol-panel"
CJK = lambda s: any("\u4e00" <= ch <= "\u9fff" for ch in s)  # noqa: E731

KV_URL = "https://game.gtimg.cn/images/bpm/web202412/kv.jpg"
ND_BG_URL = "https://game.gtimg.cn/images/bpm/web202412/news-detail-bg.jpg"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class ChatReplyLanguageTests(unittest.TestCase):
    """main.py 里 plain_result 的文案必须是中文。"""

    @staticmethod
    def _plain_result_literals() -> list[tuple[str, str]]:
        tree = ast.parse(_read(ROOT / "main.py"))
        out: list[tuple[str, str]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "plain_result"):
                continue
            # 找出所在函数名，help 指令是双语，单独处理
            owner = ""
            for outer in ast.walk(tree):
                if isinstance(outer, ast.AsyncFunctionDef) and node in ast.walk(outer):
                    owner = outer.name
                    break
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    out.append((owner, arg.value))
                elif isinstance(arg, ast.JoinedStr):
                    parts = [
                        v.value
                        for v in arg.values
                        if isinstance(v, ast.Constant) and isinstance(v.value, str)
                    ]
                    out.append((owner, "".join(parts)))
        return out

    def test_chat_replies_are_chinese(self):
        leftovers = [
            (owner, text)
            for owner, text in self._plain_result_literals()
            if owner != "help_cmd" and not CJK(text)
        ]
        self.assertEqual(
            leftovers, [], f"这些聊天文案还是英文：{leftovers}"
        )

    def test_help_reply_is_bilingual(self):
        help_texts = [t for owner, t in self._plain_result_literals() if owner == "help_cmd"]
        self.assertEqual(len(help_texts), 1)
        text = help_texts[0]
        self.assertTrue(CJK(text), "help 指令应该带中文说明")
        self.assertIn("announcement list", text, "help 指令应该保留英文对照")
        self.assertIn("分类：", text)

    def test_no_english_in_news_text_labels(self):
        """最新公告消息体的字段名必须是中文。"""
        src = _read(ROOT / "main.py")
        for label in ("Category:", "Title:", "Date:", "Link:", "Latest announcement:"):
            self.assertNotIn(label, src, f"消息体里还有英文标签 {label!r}")


class PanelTitleTests(unittest.TestCase):
    """面板 <title> 必须跟着语言切换。"""

    def test_title_uses_i18n(self):
        html = _read(PANEL / "index.html")
        self.assertIn('data-i18n="page.title"', html)
        self.assertIn("<title", html)

    def test_i18n_dict_has_page_title(self):
        src = _read(PANEL / "i18n.js")
        self.assertIn("'page.title':", src)
        # 中英两条都要有
        en_at = src.find("'page.title': 'Blue Protocol: Star Resonance — Announcements'")
        zh_at = src.find("'page.title': 'Blue Protocol: Star Resonance — 公告面板'")
        self.assertGreater(en_at, 0, "英文 page.title 缺失")
        self.assertGreater(zh_at, 0, "中文 page.title 缺失")


class TemplateStyleTests(unittest.TestCase):
    """卡片 / 长图模板的样式与文案约定。"""

    def test_card_uses_official_kv(self):
        html = _read(ROOT / "templates" / "card.html")
        self.assertIn(KV_URL, html, "卡片必须用官方 KV 做底图")
        self.assertIn(ND_BG_URL, html, "卡片必须用官方 news-detail-bg 做分隔效果")
        self.assertIn("background-size: cover", html, "底图要铺满")
        self.assertIn("linear-gradient(135deg", html, "要有左上→右下的渐变滤镜")
        self.assertIn("brightness(", html, "底图要压暗亮度")
        self.assertIn(".card::before", html)
        self.assertIn(".card::after", html)
        self.assertIn("background-position: top left", html, "分隔效果定位在左上角")

    def test_article_uses_official_kv(self):
        html = _read(ROOT / "templates" / "article.html")
        self.assertIn(KV_URL, html, "长图顶部要有官方 KV 横幅")
        self.assertIn("发布时间：", html)
        self.assertIn("原文链接：", html)

    def test_templates_have_no_english_labels(self):
        for name in ("card.html", "article.html"):
            html = _read(ROOT / "templates" / name)
            for label in ("Published:", "Source:", "Official Announcements"):
                self.assertNotIn(label, html, f"{name} 里还有英文标签 {label!r}")


class ReadmeLocaleTests(unittest.TestCase):
    """README 单语版本与双语版本必须同步，且 metadata 指向的文件要存在。"""

    def test_readme_split_in_sync(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "split_readme.py"), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            proc.returncode, 0, f"README 单语版本不同步：\n{proc.stdout}{proc.stderr}"
        )

    def test_metadata_readmes_mapping(self):
        import yaml

        meta = yaml.safe_load(_read(ROOT / "metadata.yaml"))
        readmes = meta.get("readmes") or {}
        self.assertTrue(readmes, "metadata.yaml 应当声明 readmes")
        self.assertEqual(readmes.get("default"), "README.md")
        for locale, rel in readmes.items():
            if locale == "default":
                continue
            self.assertTrue(
                (ROOT / rel).is_file(), f"readmes.{locale} 指向的 {rel} 不存在"
            )
            self.assertFalse(rel.startswith("/"), "readmes 路径必须是插件目录内的相对路径")
            self.assertNotIn("..", rel, "readmes 路径不能逃出插件目录")

    def test_chinese_readme_has_no_english_paragraph(self):
        zh = _read(ROOT / "README_zh.md")
        # 共享头部（标题 + 双语简介）本来就双语，只查「# 中文」之后的中文正文
        body = zh[zh.find("# 中文"):]
        english_lines = [
            line
            for line in body.splitlines()
            if len(line) > 40
            and not CJK(line)
            and sum(1 for ch in line if "A" <= ch <= "z") > len(line) * 0.6
        ]
        self.assertEqual(english_lines, [], "中文 README 里混进了整段英文")


class LocaleResourceTests(unittest.TestCase):
    """AstrBot 侧的 locale 文件。"""

    def test_locale_files_have_views(self):
        for locale in ("zh-CN", "en-US"):
            data = json.loads(
                _read(ROOT / ".astrbot-plugin" / "i18n" / f"{locale}.json")
            )
            views = data.get("views") or {}
            self.assertIn("blueprotocol-panel", views, f"{locale}.json 缺少 views 条目")
            self.assertTrue(views["blueprotocol-panel"].get("title"))

    def test_panel_push_reason_messages_exist(self):
        """后端返回英文 message，面板按 reason 自己出文案，这几个键都要有。"""
        src = _read(PANEL / "i18n.js")
        for reason in ("no_groups", "no_list", "fetch_failed", "up_to_date", "ok"):
            self.assertIn(f"'push.reason.{reason}':", src, f"缺少 push.reason.{reason}")
        self.assertIn("pushMessage", _read(PANEL / "app.js"))


if __name__ == "__main__":
    unittest.main()
