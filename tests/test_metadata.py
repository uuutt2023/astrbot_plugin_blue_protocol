# -*- coding: utf-8 -*-
"""打包契约测试：metadata.yaml / _conf_schema.json / i18n / 目录名必须对得上。

    python tests/test_metadata.py
全绿打印 OK。

重点防两类坑：
1. YAML 里带冒号的值（``Blue Protocol: Star Resonance``）没加引号 →
   ``yaml.safe_load`` 直接抛 ScannerError，插件装不上。
2. 插件目录名、metadata 的 name、面板目录名、i18n 的 pages 键对不上 →
   AstrBot 找不到插件或找不到面板。
"""
import json
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

PLUGIN_NAME = "astrbot_plugin_blue_protocol"


def _read(*parts):
    with open(os.path.join(_ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def test_metadata_yaml_parses():
    """用 AstrBot 同款 yaml.safe_load 校验 —— 装不上插件的元数据就在这里。"""
    try:
        import yaml
    except ImportError:  # 本机没装 PyYAML 就跳过（AstrBot 侧一定有）
        print("    (skipped: PyYAML not installed)")
        return
    metadata = yaml.safe_load(_read("metadata.yaml"))
    assert isinstance(metadata, dict), "metadata.yaml 顶层必须是 mapping"
    for key in ("name", "display_name", "short_desc", "desc", "version", "author", "repo"):
        assert key in metadata and str(metadata[key]).strip(), f"metadata 缺少 {key}"
    assert metadata["name"] == PLUGIN_NAME, metadata["name"]
    assert metadata["display_name"] == "Blue Protocol: Star Resonance"
    assert metadata["astrbot_version"], "缺少 astrbot_version"
    assert isinstance(metadata.get("support_platforms"), list)


def test_metadata_yaml_has_no_bare_colon_values():
    """值里带 ': ' 的必须加引号，否则 YAML 当成嵌套 mapping 直接报错。"""
    problems = []
    for lineno, line in enumerate(_read("metadata.yaml").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        if ":" not in stripped:
            continue
        _key, _sep, value = stripped.partition(":")
        value = value.strip()
        if not value or value.startswith(('"', "'", "[", "{", "|", ">")):
            continue
        if ": " in value or value.endswith(":"):
            problems.append((lineno, stripped))
    assert not problems, f"这些值里有裸冒号，需要加引号：{problems}"


def test_conf_schema_is_valid_json():
    schema = json.loads(_read("_conf_schema.json"))
    assert isinstance(schema, dict) and schema
    for key in ("news_groups", "list_page_size", "shot_enabled", "shot_max_height", "shot_quality"):
        assert key in schema, f"配置项缺少 {key}"
    for key, spec in schema.items():
        assert isinstance(spec, dict), key
        assert spec.get("type"), f"{key} 缺 type"
        assert spec.get("description"), f"{key} 缺 description"
    # shot_max_height / shot_quality 的上下界，面板校验用同一套
    assert isinstance(schema["shot_max_height"]["default"], int)
    assert 1 <= schema["shot_quality"]["default"] <= 100


def test_i18n_matches_panel_dir():
    i18n = json.loads(_read(".astrbot-plugin", "i18n", "zh-CN.json"))
    pages = i18n.get("pages") or {}
    assert pages, "i18n 里没有 pages 配置"
    panel_dirs = {
        d for d in os.listdir(os.path.join(_ROOT, "pages"))
        if os.path.isdir(os.path.join(_ROOT, "pages", d))
    }
    for key in pages:
        assert key in panel_dirs, f"i18n 里的 {key} 没有对应的 pages/{key} 目录"
    for key in panel_dirs:
        assert key in pages, f"pages/{key} 缺少 i18n 条目"
    meta = i18n.get("metadata") or {}
    assert meta.get("display_name") == "Blue Protocol: Star Resonance"


def test_plugin_files_present():
    """插件运行时依赖的文件都得在包里。"""
    required = [
        "main.py",
        "metadata.yaml",
        "_conf_schema.json",
        "requirements.txt",
        "logo.png",
        "README.md",
        "LICENSE",
        os.path.join("bpnews", "__init__.py"),
        os.path.join("bpnews", "api.py"),
        os.path.join("bpnews", "render.py"),
        os.path.join("bpnews", "screenshot.py"),
        os.path.join("bpnews", "groups.py"),
        os.path.join("bpnews", "page.py"),
        os.path.join("templates", "article.html"),
        os.path.join("templates", "card.html"),
        os.path.join("pages", "blueprotocol-panel", "index.html"),
        os.path.join("pages", "blueprotocol-panel", "shell.js"),
        os.path.join("pages", "blueprotocol-panel", "app.js"),
        os.path.join("pages", "blueprotocol-panel", "style.css"),
        os.path.join("pages", "blueprotocol-panel", "blueprotocol-icon.png"),
    ]
    missing = [p for p in required if not os.path.isfile(os.path.join(_ROOT, p))]
    assert not missing, f"缺少文件：{missing}"


def test_requirements_cover_imports():
    req = _read("requirements.txt").lower()
    for pkg in ("httpx", "playwright", "pillow"):
        assert pkg in req, f"requirements.txt 缺 {pkg}"


def test_no_chinese_command_triggers():
    """指令已全部改成英文，源码里不该再出现中文指令前缀。"""
    main_src = _read("main.py")
    assert "星痕共鸣公告列表" not in main_src
    assert "星痕最新公告" not in main_src
    # 英文前缀必须在
    assert re.search(r'\(?:bp\|blue\\s\*protocol\)', main_src), "找不到英文指令前缀"


def main():
    tests = [
        (name, obj)
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for name, fn in tests:
        fn()
        print(f"  {name} ok")
    print(f"OK ({len(tests)} tests)")


if __name__ == "__main__":
    main()
