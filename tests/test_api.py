# -*- coding: utf-8 -*-
"""数据层（bpnews/api.py）单测：JSONP 剥壳 / 字段归一 / 摘要 / 分页 URL。

    python tests/test_api.py
全绿打印 OK。

不联网：``fetch_*`` 的 ``_http_get`` 被替换成返回固定文本的桩。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bpnews import api  # noqa: E402


# ---------------------------------------------------------------------------
# 固定样本（按官网接口的真实返回裁剪）
# ---------------------------------------------------------------------------

LIST_JSONP = (
    'var NewsObj5014741213624121={"data":"","from":"go","status":0,"msg":{'
    '"page":2,"pagesize":2,"total":125,"totalpage":63,"result":['
    '{"iNewsId":"18951093","sTitle":"11月12日例行维护公告",'
    '"sIdxTime":"2026-11-12 11:02:25","sCreated":"2026-11-12 10:49:03",'
    '"sDesc":"11月12日例行维护公告","sTagIds":"136246",'
    '"sIMG":"//static.gametalk.qq.com/image/440/1794451733_a.png",'
    '"sCoverMap":"{\\"One\\":{\\"H\\":1440,\\"S\\":6131494,\\"Url\\":\\"//x/y.png\\",\\"W\\":2560}}"},'
    '{"iNewsId":"18950479","sTitle":"11月12日例行维护预告",'
    '"sIdxTime":"2026-11-11 17:50:46","sTagIds":"136245,136244","sIMG":""}'
    "]}};"
)

DETAIL_JSONP = (
    'var searchObj={"msg":{"iNewsId":"18951093","sTitle":"11月12日例行维护公告",'
    '"sIdxTime":"2026-11-12 11:02:25","sDesc":"11月12日例行维护公告",'
    '"sTagIds":"136246","sIMG":"//static.gametalk.qq.com/image/440/cover.png",'
    '"sContent":"<p>冒险者，您好！<br />《星痕共鸣》已于11月12日8:00至11:00进行例行维护，'
    '本次维护预计停服180分钟。<br />维护结束后，冒险者预计将通过游戏内邮件，收到蔷薇宝石（绑定）'
    '&times;700的例行维护补给。</p><p>&nbsp;</p>"},'
    '"data":"","from":"go","status":0};'
)


# ---------------------------------------------------------------------------
# JSONP 剥壳
# ---------------------------------------------------------------------------


def test_extract_json_object_handles_braces_in_strings():
    """sCoverMap 是转义后的 JSON 字符串，里面的花括号不能算进配对。"""
    obj = api.extract_json_object(LIST_JSONP)
    assert obj.startswith("{") and obj.endswith("}")
    assert '"sCoverMap":"{\\"One\\"' in obj
    assert api.extract_json_object('var x = {"a":1};') == '{"a":1}'
    # 纯 JSON（没有 var 壳）也能剥
    assert api.extract_json_object('{"a":1}') == '{"a":1}'


def test_parse_jsonp():
    data = api.parse_jsonp(LIST_JSONP)
    assert data["status"] == 0
    assert len(data["msg"]["result"]) == 2
    assert data["msg"]["total"] == 125
    # 详情
    detail = api.parse_jsonp(DETAIL_JSONP)
    assert detail["msg"]["sTitle"] == "11月12日例行维护公告"


def test_parse_jsonp_errors():
    for bad in ("", "   ", "not json at all"):
        try:
            api.parse_jsonp(bad)
        except ValueError:
            continue
        raise AssertionError(f"应该抛 ValueError: {bad!r}")
    try:
        api.parse_jsonp("var x = {oops};")
    except ValueError:
        return
    raise AssertionError("非法 JSON 应该抛 ValueError")


# ---------------------------------------------------------------------------
# 字段归一
# ---------------------------------------------------------------------------


def test_normalize_cover():
    assert api.normalize_cover("//static.gametalk.qq.com/a.png") == (
        "https://static.gametalk.qq.com/a.png"
    )
    assert api.normalize_cover("https://x/y.png") == "https://x/y.png"
    assert api.normalize_cover("/a.png") == "https://static.gametalk.qq.com/a.png"
    assert api.normalize_cover("") == ""
    assert api.normalize_cover(None) == ""


def test_tag_label():
    assert api.tag_label("136246") == "Notice"
    assert api.tag_label("136245,136244") == "News/General"
    assert api.tag_label("") == ""
    assert api.tag_label("999999") == ""


def test_parse_list_item():
    msg = api.parse_jsonp(LIST_JSONP)["msg"]
    it = api.parse_list_item(msg["result"][0])
    assert it["news_id"] == "18951093"
    assert it["title"] == "11月12日例行维护公告"
    assert it["time"] == "2026-11-12 11:02:25"
    assert it["tag"] == "Notice"
    assert it["cover"].startswith("https://")
    assert it["url"] == "https://gm.qq.com/web202503/news-detail.html?newsid=18951093"
    # 第二条：多标签 + 空封面
    it2 = api.parse_list_item(msg["result"][1])
    assert it2["tag"] == "News/General"
    assert it2["cover"] == ""


def test_parse_list_item_skips_broken():
    assert api.parse_list_item({"sTitle": "没有 id"}) == {}
    assert api.parse_list_item({"iNewsId": "1"}) == {}
    assert api.parse_list_item({}) == {}


def test_parse_detail():
    msg = api.parse_jsonp(DETAIL_JSONP)["msg"]
    d = api.parse_detail(msg)
    assert d["news_id"] == "18951093"
    assert d["title"] == "11月12日例行维护公告"
    assert d["tag"] == "Notice"
    assert "停服180分钟" in d["content"]
    assert d["url"].endswith("newsid=18951093")


# ---------------------------------------------------------------------------
# HTML → 文本
# ---------------------------------------------------------------------------


def test_html_to_text():
    text = api.html_to_text(
        "<p>第一行<br />第二行</p><p>&ldquo;引号&rdquo; &times;700 &nbsp;结尾</p>"
    )
    assert "第一行" in text and "第二行" in text
    assert "“引号”" in text
    assert "×700" in text
    assert "\u00a0" not in text
    assert "<p>" not in text


def test_html_to_text_empty():
    assert api.html_to_text("") == ""
    assert api.html_to_text("   ") == ""


def test_summarize_skips_greeting():
    """正文第一句常是「冒险者，您好！」，摘要里要跳过。"""
    msg = api.parse_jsonp(DETAIL_JSONP)["msg"]
    s = api.summarize(msg["sContent"])
    assert "冒险者，您好" not in s
    assert s.startswith("《星痕共鸣》已于11月12日")
    assert len(s) <= 201  # 200 字 + 省略号


def test_summarize_limit():
    html = "<p>" + ("字" * 500) + "</p>"
    s = api.summarize(html, limit=50)
    assert len(s) <= 51 and s.endswith("…")


def test_summarize_empty():
    assert api.summarize("") == ""


# ---------------------------------------------------------------------------
# URL 拼装（分页参数在这里）
# ---------------------------------------------------------------------------


def test_build_list_url_paging():
    url = api.build_list_url(page=3, page_size=8)
    assert "page=3" in url and "pagesize=8" in url
    assert "p0=440" in url and "source=web_pc" in url
    assert "order=sIdxTime" in url and "type=iTag" in url
    assert f"id={api.TAG_ALL}" in url
    assert url.startswith("https://apps.game.qq.com/wmp/v3.1/?")


def test_build_list_url_clamps():
    """页码/条数非法时夹到合法范围，不要把 0 页发给接口。"""
    assert "page=1" in api.build_list_url(page=0)
    assert "page=1" in api.build_list_url(page=-5)
    assert "pagesize=1" in api.build_list_url(page_size=0)
    assert "pagesize=1" in api.build_list_url(page_size=-1)


def test_resolve_tag_and_display_name():
    """英文分类别名 → 标签 id；标签 id → 英文展示名。"""
    assert api.resolve_tag("notice") == "136246"
    assert api.resolve_tag("NOTICE") == "136246"   # 大小写不敏感
    assert api.resolve_tag(" announcements ") == "136246"
    assert api.resolve_tag("ann") == "136246"
    assert api.resolve_tag("news") == "136245"
    assert api.resolve_tag("events") == "136247"
    assert api.resolve_tag("activity") == "136247"
    assert api.resolve_tag("all") == api.TAG_ALL
    assert api.resolve_tag("latest") == api.TAG_ALL
    assert api.resolve_tag("公告") == ""            # 认不出来的返回空串
    assert api.resolve_tag("") == ""
    assert api.tag_display_name("136246") == "Notice"
    assert api.tag_display_name("136247") == "Event"
    assert api.tag_display_name("999999") == ""


def test_build_list_url_tag():
    url = api.build_list_url(tag_id=api.resolve_tag("notice"))
    assert "id=136246" in url
    assert api.resolve_tag("news") == "136245"
    assert api.resolve_tag("event") == "136247"


def test_build_detail_url():
    url = api.build_detail_url(18951093)
    assert url.startswith("https://apps.game.qq.com/wmp/v3.1/public/searchNews.php?")
    assert "id=18951093" in url and "p0=440" in url


def test_article_url():
    assert api.article_url("18951093") == (
        "https://gm.qq.com/web202503/news-detail.html?newsid=18951093"
    )


# ---------------------------------------------------------------------------
# fetch_*（桩掉网络）
# ---------------------------------------------------------------------------


def test_fetch_list_parses_paging_info():
    async def fake(url, timeout=15):
        fake.last = url
        return LIST_JSONP

    fake.last = ""
    original = api._http_get
    api._http_get = fake
    try:
        import asyncio

        items, info = asyncio.run(api.fetch_list(page=2, page_size=2))
    finally:
        api._http_get = original
    assert "page=2" in fake.last and "pagesize=2" in fake.last
    assert len(items) == 2
    assert info == {"page": 2, "pagesize": 2, "total": 125, "totalpage": 63}


def test_fetch_detail_parses_content():
    async def fake(url, timeout=15):
        return DETAIL_JSONP

    original = api._http_get
    api._http_get = fake
    try:
        import asyncio

        d = asyncio.run(api.fetch_detail("18951093"))
    finally:
        api._http_get = original
    assert d["title"] == "11月12日例行维护公告"
    assert "sContent" not in d
    assert "停服180分钟" in d["content"]


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
