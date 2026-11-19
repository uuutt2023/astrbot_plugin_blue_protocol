# -*- coding: utf-8 -*-
"""把双语 README.md 拆成单语版本，供 AstrBot 插件页按语言切换。

AstrBot 支持在 metadata.yaml 里声明多语言 README：

    readmes:
      default: README.md
      zh-CN: README_zh.md
      en-US: README_en.md

README.md 本身保持双语（英文在前、中文在后），这样：
  * GitHub 首页一眼能看到两种语言；
  * 不支持 readmes 的旧版 AstrBot 仍然能拿到完整文档。

拆分规则：以 `# English` 和 `# 中文` 两个一级标题为界。
  * 共享头部（标题与双语简介）同时进三份文件；
  * `# English` 到 `# 中文` 之间是英文段；
  * `# 中文` 之后是中文段。

用法：
    python tools/split_readme.py          # 生成 README_en.md / README_zh.md
    python tools/split_readme.py --check  # 只校验，不写文件（CI / 测试用）
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
EN_README = ROOT / "README_en.md"
ZH_README = ROOT / "README_zh.md"

EN_HEADING = "# English"
ZH_HEADING = "# 中文"


def split(text: str) -> tuple[str, str, str]:
    """返回 (共享头部, 英文段, 中文段)。"""
    en_at = text.find(EN_HEADING)
    zh_at = text.find(ZH_HEADING)
    if en_at < 0 or zh_at < 0 or en_at > zh_at:
        raise RuntimeError(
            "README.md 里必须同时存在 '# English' 与 '# 中文' 两个一级标题，"
            "且 '# English' 在前"
        )
    shared = text[:en_at]
    english = text[en_at:zh_at]
    chinese = text[zh_at:]
    return shared, english, chinese


def build(text: str) -> dict[Path, str]:
    shared, english, chinese = split(text)
    return {
        README: text,
        EN_README: shared + english.rstrip() + "\n",
        ZH_README: shared + chinese.rstrip() + "\n",
    }


def main(argv: list[str]) -> int:
    text = README.read_text(encoding="utf-8")
    files = build(text)
    if "--check" in argv:
        bad = []
        for path, want in files.items():
            if path == README:
                continue
            have = path.read_text(encoding="utf-8") if path.is_file() else ""
            if have != want:
                bad.append(path.name)
        if bad:
            print("README 单语版本与 README.md 不同步：" + ", ".join(bad))
            print("请运行 python tools/split_readme.py 重新生成")
            return 1
        print("README 单语版本与 README.md 同步 ✓")
        return 0
    for path, content in files.items():
        if path == README:
            continue
        path.write_text(content, encoding="utf-8")
        print(f"写入 {path.name}（{len(content.encode('utf-8'))} bytes）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
