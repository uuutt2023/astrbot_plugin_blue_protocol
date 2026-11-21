# -*- coding: utf-8 -*-
"""Blue Protocol: Star Resonance main.py 冒烟测试：桩掉 astrbot 把插件类拉起来，测面板接线与推送逻辑。

    python tests/test_blueprotocol_main.py
全绿打印 OK。

覆盖：import 健全性 / 11 个面板接口注册 / 群名记录（事件自带 + 后台问平台）/
刷新群列表 / 一次推送的去重与强制重发 / _tick 节流 / 指令参数解析 / terminate 落盘。
"""
import asyncio
import json
import os
import sys
import tempfile
import types

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLUGIN_ROOT)


class _Logger:
    def info(self, *a, **k):
        pass

    warning = error = debug = info


class _EventMessageType:
    ALL = "all"


def _passthrough(*d_args, **d_kwargs):
    def deco(func):
        return func

    return deco


class _Star:
    def __init__(self, context=None):
        self.context = context

    async def html_render(self, tmpl, data, options=None):
        return "http://t2i/card.png"


_FILTER = types.SimpleNamespace(
    regex=_passthrough,
    event_message_type=_passthrough,
    on_astrbot_loaded=_passthrough,
    EventMessageType=_EventMessageType,
)

_DATA_ROOT = tempfile.mkdtemp(prefix="bpnews-main-")


def _install_astrbot_stub():
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    api.logger = _Logger()
    api.AstrBotConfig = dict

    event_mod = types.ModuleType("astrbot.api.event")
    event_mod.filter = _FILTER
    event_mod.AstrMessageEvent = object

    class _MessageChain:
        def message(self, text):
            return self

        def url_image(self, url):
            return self

        def file_image(self, path):
            return self

    event_mod.MessageChain = _MessageChain

    star_mod = types.ModuleType("astrbot.api.star")
    star_mod.Context = object
    star_mod.Star = _Star
    star_mod.StarTools = types.SimpleNamespace(
        get_data_dir=lambda name="": _DATA_ROOT
    )

    core = types.ModuleType("astrbot.core")
    core_utils = types.ModuleType("astrbot.core.utils")
    path_mod = types.ModuleType("astrbot.core.utils.astrbot_path")
    path_mod.get_astrbot_data_path = lambda: _DATA_ROOT
    core.utils = core_utils
    core_utils.astrbot_path = path_mod

    api.star = star_mod
    api.event = event_mod
    astrbot.api = api
    astrbot.core = core

    sys.modules["astrbot"] = astrbot
    sys.modules["astrbot.api"] = api
    sys.modules["astrbot.api.event"] = event_mod
    sys.modules["astrbot.api.star"] = star_mod
    sys.modules["astrbot.core"] = core
    sys.modules["astrbot.core.utils"] = core_utils
    sys.modules["astrbot.core.utils.astrbot_path"] = path_mod


_install_astrbot_stub()

from bpnews import page as page_mod  # noqa: E402
import main as bp_main  # noqa: E402


# ---------------------------------------------------------------------------
# 假对象
# ---------------------------------------------------------------------------


class FakeQuery:
    def __init__(self, data):
        self._data = {k: str(v) for k, v in (data or {}).items()}

    def get(self, key, default=""):
        return self._data.get(key, default)


class FakeRequest:
    def __init__(self, query=None, body=None, method="GET"):
        self.query = FakeQuery(query)
        self.args = self.query
        self.method = method
        self._body = body

    async def json(self, default=None):
        return self._body if self._body is not None else default


class FakeContext:
    def __init__(self, platform_insts=None, send_ok=True):
        self.routes = []
        self._insts = list(platform_insts or [])
        # 真实 AstrBot 两套取法都有，这里保持一致
        self.platform_manager = types.SimpleNamespace(
            platform_insts=self._insts,
            get_insts=lambda: list(self._insts),
        )
        self.sent = []
        self.send_ok = send_ok

    def register_web_api(self, path, handler, methods, desc):
        self.routes.append((path, handler, tuple(methods), desc))

    async def send_message(self, umo, chain):
        if not self.send_ok:
            raise RuntimeError("发送失败")
        self.sent.append(umo)


class FakeClient:
    def __init__(self, group_info=None, group_list=None, fail=False):
        self._info = group_info or {}
        self._list = group_list or []
        self._fail = fail
        self.calls = []

    async def call_action(self, action, **kwargs):
        self.calls.append((action, kwargs))
        if self._fail:
            raise RuntimeError("平台炸了")
        return self._list if action == "get_group_list" else self._info


class FakePlatformInst:
    def __init__(self, platform_id, client, adapter="aiocqhttp"):
        self._pid = platform_id
        self._client = client
        self._adapter = adapter

    def meta(self):
        return types.SimpleNamespace(id=self._pid, name=self._adapter)

    def get_client(self):
        return self._client


def make_event(
    text="bp list",
    umo="napcat:GroupMessage:1001",
    gid="1001",
    group_name=None,
    bot=None,
):
    ev = types.SimpleNamespace(
        message_str=text,
        unified_msg_origin=umo,
        message_obj=types.SimpleNamespace(
            group_id=gid,
            group=types.SimpleNamespace(group_id=gid, group_name=group_name),
        ),
    )
    ev.get_platform_id = lambda: "napcat"
    if bot is not None:
        ev.bot = bot
    return ev


def make_plugin(platform_insts=None, **cfg):
    """新数据目录 + 假 context + 真插件实例；返回插件、context、数据目录。"""
    data_dir = tempfile.mkdtemp(prefix="bpnews-case-")
    bp_main.DATA_DIR = None
    bp_main.get_astrbot_data_path = lambda: data_dir
    ctx = FakeContext(platform_insts=platform_insts)
    plugin = bp_main.BlueProtocolNewsPlugin(ctx, cfg)
    return plugin, ctx, plugin.data_dir


def run(coro):
    return asyncio.run(coro)


NEWS_ITEM = {
    "news_id": "18951093",
    "tag": "公告",
    "title": "11月12日例行维护公告",
    "time": "2026-11-12 11:02:25",
    "desc": "11月12日例行维护公告",
    "cover": "https://static.gametalk.qq.com/image/440/a.png",
    "url": "https://gm.qq.com/web202503/news-detail.html?newsid=18951093",
}

NEWS_DETAIL = {
    **NEWS_ITEM,
    "content": "<p>冒险者，您好！<br />《星痕共鸣》已于11月12日8:00至11:00进行例行维护。</p>",
}

PAGE_INFO = {"page": 1, "pagesize": 10, "total": 125, "totalpage": 13}


def _async(value):
    async def _inner(*a, **k):
        return value

    return _inner


def patch_pipeline(plugin):
    """把网络相关的几个模块函数换成本地桩，只测推送流程本身。"""
    calls = {"send_text": [], "send_img": []}
    bp_main.fetch_news_list = _async(([dict(NEWS_ITEM)], dict(PAGE_INFO)))
    bp_main.fetch_detail = _async(dict(NEWS_DETAIL))
    bp_main.fetch_summary_cached = _async("这是摘要")

    async def _news_image(it, detail, summary):
        return None, ""

    async def _send_text_to(umo, text):
        calls["send_text"].append((umo, text))

    async def _send_img_to(umo, url):
        calls["send_img"].append((umo, url))

    plugin._news_image = _news_image
    plugin._send_text_to = _send_text_to
    plugin._send_img_to = _send_img_to
    return calls


def route_paths(ctx):
    return [path for path, *_ in ctx.routes]


# ---------------------------------------------------------------------------
# import 与面板接线
# ---------------------------------------------------------------------------


def test_import_and_routes():
    plugin, ctx, _ = make_plugin()
    assert bp_main.BlueProtocolNewsPlugin is not None
    assert page_mod.PLUGIN_NAME == "astrbot_plugin_blue_protocol"
    paths = route_paths(ctx)
    for suffix in (
        "/page/meta",
        "/page/status",
        "/page/groups",
        "/page/groups/save",
        "/page/push-now",
        "/page/records",
        "/page/records/reset",
        "/page/shots",
        "/page/shots/clear",
        "/page/cache/clear",
        "/page/config/save",
    ):
        assert f"/astrbot_plugin_blue_protocol{suffix}" in paths, suffix
    assert plugin.page.plugin is plugin
    assert plugin.page.data_dir == plugin.data_dir
    assert plugin.groups.path.name == "groups.json"


def test_push_groups_normalizes_bare_ids():
    plugin, _, _ = make_plugin(news_groups=["1001", "napcat:GroupMessage:1002", "1001"])
    assert plugin._push_groups() == [
        "aiocqhttp:GroupMessage:1001",
        "napcat:GroupMessage:1002",
    ]


def test_bare_group_number_gets_routable_instance_id():
    """裸群号要补成**实例 id**：写 aiocqhttp 这种适配器类型名的话 send_message 匹配不到。"""
    insts = [
        FakePlatformInst("webchat", None, adapter="webchat"),
        FakePlatformInst("napcat", None, adapter="aiocqhttp"),
    ]
    plugin, _, _ = make_plugin(platform_insts=insts, news_groups=["1001"])
    assert plugin._bare_id_platform() == "napcat"
    assert plugin._push_groups() == ["napcat:GroupMessage:1001"]

    # 只有 webchat 时也不能写死 aiocqhttp
    only_web = [FakePlatformInst("webchat", None, adapter="webchat")]
    plugin2, _, _ = make_plugin(platform_insts=only_web, news_groups=["1001"])
    assert plugin2._bare_id_platform() == "webchat"

    # 探不到平台：保持旧行为（回落 aiocqhttp）
    plugin3, _, _ = make_plugin(news_groups=["1001"])
    assert plugin3._bare_id_platform() == "aiocqhttp"


def test_plugin_status_route_works_end_to_end():
    plugin, _, _ = make_plugin(news_groups=["1001"])
    run(plugin.on_any_message(make_event(group_name="Blue Protocol Fans")))
    page_mod.request = FakeRequest()
    resp = run(plugin.page.get_status())
    page_mod.request = None
    payload = resp["data"]
    assert payload["status"] == "ok"
    assert payload["data"]["groups"][0]["label"] == "Blue Protocol Fans（1001）"


# ---------------------------------------------------------------------------
# 指令参数解析
# ---------------------------------------------------------------------------


def test_command_prefixes():
    """bp / blue protocol / blueprotocol 三个前缀都认。"""
    for text in ("bp list", "blue protocol list", "blueprotocol list"):
        assert bp_main.re.match(bp_main.T_LIST, text), text
    for text in ("bp latest", "blue protocol latest", "blueprotocol latest"):
        assert bp_main.re.match(bp_main.T_LATEST, text), text
    for text in ("bp push on", "blue protocol push on"):
        assert bp_main.re.match(bp_main.T_PUSH, text), text
    assert bp_main.re.match(bp_main.T_HELP, "bp help")
    assert bp_main.re.match(bp_main.T_RESET, "bp reset")
    # 「latest dedup」不能被「latest」抢走
    assert not bp_main.re.match(bp_main.T_LATEST, "bp latest dedup")
    # 中文指令不再触发
    for text in ("星痕共鸣公告列表", "星痕最新公告", "天刀公告列表"):
        assert not bp_main.re.match(bp_main.T_LIST, text), text
        assert not bp_main.re.match(bp_main.T_LATEST, text), text


def test_parse_list_args():
    plugin, _, _ = make_plugin()
    cases = {
        "bp list": ("", 1),
        "bp list 2": ("", 2),
        "bp list notice": ("notice", 1),
        "bp list notice 3": ("notice", 3),
        "bp list news 2": ("news", 2),
        "bp list event": ("event", 1),
        "bp list all": ("all", 1),
        "blue protocol list announcement 4": ("announcement", 4),
        "blueprotocol list ann 5": ("ann", 5),
    }
    for text, expected in cases.items():
        got = plugin._parse_list_args(make_event(text=text))
        assert got == expected, (text, got, expected)


def test_push_command_argument():
    plugin, _, _ = make_plugin()
    for text, expected in (
        ("bp push on", "on"),
        ("bp push off", "off"),
        ("bp push status", "status"),
        ("bp push test", "test"),
        ("bp push", ""),
        ("blue protocol push on", "on"),
    ):
        assert plugin._cap(bp_main.T_PUSH, make_event(text=text)) == expected, text


# ---------------------------------------------------------------------------
# 群名记录
# ---------------------------------------------------------------------------


def test_remember_group_from_event():
    plugin, _, _ = make_plugin()
    run(plugin.on_any_message(make_event(group_name="Blue Protocol Fans")))
    assert plugin.groups.name_of("napcat:GroupMessage:1001") == "Blue Protocol Fans"
    # 落盘了（面板不用等新消息）
    assert plugin.groups.path.is_file()
    # 事件不带群名时保持「群 群号」，不写空名
    run(plugin.on_any_message(make_event(umo="napcat:GroupMessage:2002", gid="2002")))
    assert plugin.groups.name_of("napcat:GroupMessage:2002") == ""
    assert plugin.groups.label("napcat:GroupMessage:2002") == "群 2002"


def test_learn_group_name_from_platform():
    plugin, _, _ = make_plugin()
    client = FakeClient(
        group_info={"group_id": 1001, "group_name": "Blue Protocol Fans", "member_count": 300}
    )
    run(plugin._learn_group_name(client, "napcat:GroupMessage:1001", "1001", "napcat"))
    assert client.calls[0] == ("get_group_info", {"group_id": 1001})
    assert plugin.groups.name_of("napcat:GroupMessage:1001") == "Blue Protocol Fans"
    # 平台失败：静默
    bad = FakeClient(fail=True)
    run(plugin._learn_group_name(bad, "napcat:GroupMessage:1003", "1003", "napcat"))
    assert plugin.groups.name_of("napcat:GroupMessage:1003") == ""


def test_refresh_group_names_from_platform():
    client = FakeClient(
        group_list=[
            {"group_id": 1001, "group_name": "Blue Protocol Fans", "member_count": 300},
            {"group_id": 2002, "group_name": "活动群"},
        ]
    )
    plugin, _, _ = make_plugin(platform_insts=[FakePlatformInst("napcat", client)])
    changed = run(plugin.refresh_group_names(force=True))
    assert changed == 2
    assert plugin.groups.name_of("napcat:GroupMessage:2002") == "活动群"
    # 节流：刚刷过再刷不带 force 就不打接口了
    assert run(plugin.refresh_group_names()) == 0
    assert len(client.calls) == 1
    # 平台接口炸了也不抛
    bad, _, _ = make_plugin(platform_insts=[FakePlatformInst("napcat", FakeClient(fail=True))])
    assert run(bad.refresh_group_names(force=True)) == 0
    # 没有平台管理器（老版本 AstrBot）也不报错
    plain, _, _ = make_plugin()
    plain.context.platform_manager = types.SimpleNamespace()
    assert run(plain.refresh_group_names(force=True)) == 0


def test_save_config_now_prefers_async():
    plugin, _, _ = make_plugin()

    class Cfg(dict):
        def __init__(self):
            super().__init__()
            self.sync = 0
            self.async_calls = 0

        def save_config(self):
            self.sync += 1

        async def save_config_async(self):
            self.async_calls += 1

    cfg = Cfg()
    plugin.config = cfg
    run(plugin.save_config_now())
    assert cfg.async_calls == 1 and cfg.sync == 0

    cfg2 = Cfg()
    del Cfg.save_config_async
    plugin.config = cfg2
    run(plugin.save_config_now())
    assert cfg2.sync == 1


# ---------------------------------------------------------------------------
# 推送流程
# ---------------------------------------------------------------------------


def test_push_round_no_groups():
    plugin, _, _ = make_plugin()
    result = run(plugin._push_round())
    assert result["reason"] == "no_groups" and result["pushed"] == []
    assert "No push targets" in result["message"]


def test_push_round_dedup_and_force():
    plugin, _, data_dir = make_plugin(news_groups=["1001", "napcat:GroupMessage:1002"])
    calls = patch_pipeline(plugin)

    first = run(plugin._push_round())
    assert first["reason"] == "ok" and first["title"] == NEWS_ITEM["title"]
    assert sorted(first["pushed"]) == [
        "aiocqhttp:GroupMessage:1001",
        "napcat:GroupMessage:1002",
    ]
    assert len(calls["send_text"]) == 2
    # 推送给群里的正文是中文（游戏公告标题本身也是中文）
    assert "最新公告" in calls["send_text"][0][1]
    assert "标题：" in calls["send_text"][0][1]
    assert "这是摘要" in calls["send_text"][0][1]
    # 记录写盘了：每群一条 push:umo
    records = json.loads((data_dir / "push_record.json").read_text(encoding="utf-8"))
    assert set(records) == {
        "push:aiocqhttp:GroupMessage:1001",
        "push:napcat:GroupMessage:1002",
    }
    assert records["push:aiocqhttp:GroupMessage:1001"] == NEWS_ITEM["title"]

    # 再跑一轮：已推过，全部跳过
    second = run(plugin._push_round())
    assert second["reason"] == "up_to_date" and second["pushed"] == []
    assert sorted(second["skipped"]) == sorted(first["pushed"])
    assert len(calls["send_text"]) == 2

    # force：忽略记录重发
    third = run(plugin._push_round(force=True))
    assert third["reason"] == "ok" and len(third["pushed"]) == 2
    assert len(calls["send_text"]) == 4


def test_push_round_target_only():
    plugin, _, _ = make_plugin(news_groups=["1001", "1002"])
    calls = patch_pipeline(plugin)
    result = run(plugin._push_round("1002"))
    assert result["pushed"] == ["aiocqhttp:GroupMessage:1002"]
    assert [umo for umo, _ in calls["send_text"]] == ["aiocqhttp:GroupMessage:1002"]


def test_push_round_fetch_failure():
    plugin, _, _ = make_plugin(news_groups=["1001"])
    patch_pipeline(plugin)

    async def boom(*a, **k):
        raise RuntimeError("网络断了")

    bp_main.fetch_news_list = boom
    result = run(plugin._push_round())
    assert result["reason"] == "fetch_failed" and "网络断了" in result["message"]

    bp_main.fetch_news_list = _async(([], dict(PAGE_INFO)))
    assert run(plugin._push_round())["reason"] == "no_list"


def test_push_now_bypasses_throttle():
    plugin, _, _ = make_plugin(news_groups=["1001"])
    patch_pipeline(plugin)
    plugin._last_check = 0
    run(plugin.push_now())
    assert plugin._last_check > 0  # 手动推送会刷新节流时间戳
    result = run(plugin.push_now("1001", force=True))
    assert result["pushed"] == ["aiocqhttp:GroupMessage:1001"]


def test_tick_throttle():
    plugin, _, _ = make_plugin(news_groups=["1001"])
    calls = patch_pipeline(plugin)

    run(plugin._tick())
    assert len(calls["send_text"]) == 1  # 第一次会推
    plugin._last_check = 9999999999.0  # 假装刚跑过
    run(plugin._tick())
    assert len(calls["send_text"]) == 1  # 节流窗口内不再跑

    # 没有推送群时直接返回，连时间戳都不动
    empty, _, _ = make_plugin()
    patch_pipeline(empty)
    empty._last_check = 0
    run(empty._tick())
    assert empty._last_check == 0


def test_terminate_flushes_group_names():
    plugin, _, data_dir = make_plugin()
    run(plugin.on_any_message(make_event(group_name="Blue Protocol Fans")))
    plugin._scheduler_task = None
    run(plugin.terminate())
    saved = json.loads((data_dir / "groups.json").read_text(encoding="utf-8"))
    assert saved["groups"]["napcat:GroupMessage:1001"]["group_name"] == "Blue Protocol Fans"


def test_norm_umo_rewrites_adapter_type_to_instance_id():
    """推送目标按平台实例 id 路由：写成适配器类型名要换成实例 id，否则静默丢消息。"""
    insts = [
        FakePlatformInst("napcat", FakeClient(), adapter="aiocqhttp"),
        FakePlatformInst("qqguan", FakeClient(), adapter="qq_official"),
    ]
    plugin, _, _ = make_plugin(platform_insts=insts)
    # 适配器类型名 → 实例 id
    assert plugin._norm_umo("aiocqhttp:GroupMessage:1001") == "napcat:GroupMessage:1001"
    assert plugin._norm_umo("qq_official:GroupMessage:OPENID") == "qqguan:GroupMessage:OPENID"
    # 已是实例 id / 认不出来的：原样，不误改
    assert plugin._norm_umo("napcat:GroupMessage:1001") == "napcat:GroupMessage:1001"
    assert plugin._norm_umo("telegram:GroupMessage:9") == "telegram:GroupMessage:9"
    # 裸群号：补到 aiocqhttp 类型的实例 id
    assert plugin._norm_umo("1001") == "napcat:GroupMessage:1001"


def test_news_image_prefers_typst_then_falls_back():
    """渲染顺序：Typst 长图 → 浏览器长图 → Typst 卡片 → html_render 卡片。"""
    plugin, _, _ = make_plugin(typst_enabled=True)
    order = []

    async def fake_typst_long(detail, data_dir, **kw):
        order.append("typst-long")
        return "/tmp/typst-long.jpg", False

    async def fake_shot(html, key, **kw):
        order.append("shot")
        return "/tmp/shot.jpg", False

    async def fake_typst_card(it, summary, data_dir, **kw):
        order.append("typst-card")
        return "/tmp/typst-card.jpg"

    async def fake_t2i(it, summary):
        order.append("t2i")
        return "https://example.com/card.jpg"

    bp_main.typst_render.render_long_image = fake_typst_long
    bp_main.typst_render.render_card = fake_typst_card
    bp_main.screenshot.shot_article = fake_shot
    plugin._render_card = fake_t2i

    path, note = run(plugin._news_image(dict(NEWS_ITEM), dict(NEWS_DETAIL), "摘要"))
    assert order == ["typst-long"], order
    assert path == "/tmp/typst-long.jpg"

    # Typst 挂掉 → 走浏览器截图
    order.clear()

    async def boom(*a, **k):
        raise RuntimeError("typst down")

    bp_main.typst_render.render_long_image = boom
    path, note = run(plugin._news_image(dict(NEWS_ITEM), dict(NEWS_DETAIL), "摘要"))
    assert order == ["shot"], order
    assert path == "/tmp/shot.jpg"

    # 浏览器也挂 → 走 Typst 卡片
    order.clear()

    async def boom_shot(*a, **k):
        raise RuntimeError("no browser")

    bp_main.screenshot.shot_article = boom_shot
    path, note = run(plugin._news_image(dict(NEWS_ITEM), dict(NEWS_DETAIL), "摘要"))
    assert order == ["typst-card"], order
    assert path == "/tmp/typst-card.jpg"

    # 全挂 → html_render 卡片
    order.clear()
    bp_main.typst_render.render_card = boom
    path, note = run(plugin._news_image(dict(NEWS_ITEM), dict(NEWS_DETAIL), "摘要"))
    assert order == ["t2i"], order
    assert path == "https://example.com/card.jpg"

    # Typst 关掉 → 不走 Typst
    order.clear()
    plugin2, _, _ = make_plugin(typst_enabled=False)
    plugin2._render_card = fake_t2i
    bp_main.screenshot.shot_article = fake_shot
    run(plugin2._news_image(dict(NEWS_ITEM), dict(NEWS_DETAIL), "摘要"))
    assert order == ["shot"], order


def test_news_image_returns_none_when_all_fail():
    """所有渲染都失败时返回 None，让上层降级成纯文字。"""
    plugin, _, _ = make_plugin(typst_enabled=True)

    async def boom(*a, **k):
        raise RuntimeError("nope")

    async def boom2(*a, **k):
        raise RuntimeError("nope")

    bp_main.typst_render.render_long_image = boom
    bp_main.screenshot.shot_article = boom2
    bp_main.typst_render.render_card = boom2

    async def boom_card(*a, **k):
        raise RuntimeError("nope")

    plugin._render_card = boom_card
    path, note = run(plugin._news_image(dict(NEWS_ITEM), dict(NEWS_DETAIL), "摘要"))
    assert path is None


def test_long_image_options_read_config():
    """长图版式配置要从 config 读到，坏值回退默认。"""
    plugin, _, _ = make_plugin(
        typst_long_width=1600,
        typst_long_body_width=1500,
        typst_long_border=50,
        typst_long_theme="light",
        typst_para_spacing=20,
        typst_line_height=2.0,
    )
    opts = plugin._long_image_options()
    assert opts["width"] == 1600
    assert opts["body_width"] == 1500
    assert opts["border"] == 50
    assert opts["theme"] == "light"
    assert opts["para_spacing"] == 20
    assert opts["line_height"] == 2.0

    default, _, _ = make_plugin(typst_enabled=True)
    opts = default._long_image_options()
    assert opts["width"] == 1280
    assert opts["body_width"] == 1258
    assert opts["border"] == 11
    assert opts["theme"] == "dark"
    assert opts["para_spacing"] == 14
    assert opts["line_height"] == 1.8


def test_news_image_passes_layout_to_typst():
    """版式参数要一路传到 Typst 渲染器。"""
    plugin, _, _ = make_plugin(
        typst_enabled=True,
        typst_long_width=1600,
        typst_long_theme="light",
        typst_long_border=30,
    )
    seen = {}

    async def fake_typst_long(detail, data_dir, **kw):
        seen.update(kw)
        return "/tmp/x.jpg", False

    bp_main.typst_render.render_long_image = fake_typst_long
    run(plugin._news_image(dict(NEWS_ITEM), dict(NEWS_DETAIL), "摘要"))
    assert seen["width"] == 1600
    assert seen["theme"] == "light"
    assert seen["border"] == 30
    assert seen["body_width"] == 1258


def test_typst_options_read_config():
    plugin, _, _ = make_plugin(typst_enabled=True, typst_ppi=180, typst_timeout=90)
    opts = plugin._typst_options()
    assert opts["ppi"] == 180 and opts["timeout"] == 90
    default, _, _ = make_plugin(typst_enabled=True)
    default = default._typst_options()
    assert default["ppi"] == 144 and default["timeout"] == 60


def test_news_text_contains_tag_and_link():
    plugin, _, _ = make_plugin()
    text = plugin._news_text(NEWS_ITEM, "摘要内容")
    assert "公告" in text
    assert NEWS_ITEM["title"] in text
    assert NEWS_ITEM["url"] in text
    assert "摘要内容" in text


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
