# -*- coding: utf-8 -*-
"""Blue Protocol: Star Resonance 官方公告插件（AstrBot）。

《蓝色协议：星痕共鸣》官方公告查询与推送：公告列表（支持分页与分类）、最新公告
（正文摘要 + 手机长图）、按群去重、定时自动推送（每 5 分钟检查，有更新自动推送），
以及一个 Web 面板用来按群名管理推送群。

指令统一用英文，前缀 ``bp``（也认 ``blue protocol`` / ``blueprotocol``），
避免与其它插件的裸词指令冲突。
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path

# AstrBot 以 data.plugins.<name> 模块名加载 main.py，需显式将插件目录加入 sys.path
_PLUGIN_ROOT = Path(__file__).resolve().parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from bpnews import api, layout, screenshot
from bpnews.typst import render as typst_render
from bpnews.api import TAG_ALL, resolve_tag, tag_display_name
from bpnews.groups import (
    SOURCE_API,
    GroupNameResolver,
    parse_group_info,
    parse_group_list,
)
from bpnews.page import NewsPageController
from bpnews.render import card_data, render_article

PLUGIN_NAME = "astrbot_plugin_blue_protocol"
GAME_NAME = "Blue Protocol: Star Resonance"

# 指令前缀：bp / blue protocol / blueprotocol 都认
_PREFIX = r"(?:bp|blue\s*protocol)"
# 给帮助文案用的人话前缀
_PREFIX_TEXT = "bp"
# 列表指令的分类参数（英文别名）
_CATEGORIES = (
    r"all|latest|notice|announcement|announcements|ann|news|event|events|activity"
)

T_LIST = rf"^{_PREFIX}\s+list(?:\s+({_CATEGORIES}))?(?:\s+(\d+))?\s*$"
T_LATEST = rf"^{_PREFIX}\s+latest\s*$"
T_LATEST_DEDUP = rf"^{_PREFIX}\s+latest\s+dedup\s*$"
T_PUSH = rf"^{_PREFIX}\s+push(?:\s+(on|off|status|test))?\s*$"
T_RESET = rf"^{_PREFIX}\s+reset\s*$"
T_HELP = rf"^{_PREFIX}\s+help\s*$"

_RE_CACHE: dict[str, re.Pattern] = {}

DATA_DIR: Path | None = None


def _data_dir() -> Path:
    global DATA_DIR
    if DATA_DIR is None:
        DATA_DIR = (
            Path(get_astrbot_data_path()) / "plugin_data" / PLUGIN_NAME
        )
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


class _RateLimit:
    def __init__(self, interval: float):
        self.interval = interval
        self._last: dict[str, float] = {}

    def ok(self, key: str) -> bool:
        now = time.time()
        if now - self._last.get(key, 0) >= self.interval:
            self._last[key] = now
            return True
        return False


# ---------------------------------------------------------------------------
# 数据获取
# ---------------------------------------------------------------------------


async def fetch_news_list(
    page: int = 1, page_size: int = 10, tag_id: str = TAG_ALL
) -> tuple[list[dict], dict]:
    """公告列表（按时间倒序）。返回 (条目, 分页信息)。"""
    items, info = await api.fetch_list(page=page, page_size=page_size, tag_id=tag_id)
    if not items:
        raise RuntimeError("no announcement data found (the API shape may have changed)")
    return items, info


async def fetch_detail(news_id: str) -> dict:
    """公告详情（含正文 HTML）。"""
    detail = await api.fetch_detail(news_id)
    if not detail:
        raise RuntimeError("announcement detail is empty")
    return detail


def summarize_detail(detail: dict) -> str:
    """正文摘要（跳过「冒险者，您好！」这类招呼语）。"""
    return api.summarize(detail.get("content") or "")


# ---------------------------------------------------------------------------
# 推送去重记录
# ---------------------------------------------------------------------------


def _load_records() -> dict:
    try:
        p = _data_dir() / "push_record.json"
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_records(records: dict) -> None:
    try:
        p = _data_dir() / "push_record.json"
        p.write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def last_pushed(key: str) -> str:
    return _load_records().get(key, "")


def mark_pushed(key: str, title: str) -> None:
    records = _load_records()
    records[key] = title
    _save_records(records)


def clear_pushed(key: str) -> None:
    records = _load_records()
    records.pop(key, None)
    _save_records(records)


# ---------------- 摘要缓存（多群推送复用，避免重复抓取） ----------------

_SUMMARY_CACHE_FILE = "summary_cache.json"


def _load_summary_cache() -> dict:
    try:
        p = _data_dir() / _SUMMARY_CACHE_FILE
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_summary_cache(cache: dict) -> None:
    try:
        p = _data_dir() / _SUMMARY_CACHE_FILE
        p.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _clean_summary_cache(cache: dict) -> None:
    """防膨胀：只留最近 100 条。"""
    if len(cache) <= 100:
        return
    for k in sorted(cache, key=lambda x: cache[x]["t"])[:-100]:
        cache.pop(k, None)


async def fetch_summary_cached(detail: dict) -> str:
    """带缓存（24h）的摘要：同一公告推多个群时只解析一次。"""
    news_id = str(detail.get("news_id") or "")
    if not news_id:
        return summarize_detail(detail)
    cache = _load_summary_cache()
    entry = cache.get(news_id)
    if entry and time.time() - entry.get("t", 0) < 86400:
        return entry.get("s", "")
    s = summarize_detail(detail)
    cache[news_id] = {"t": time.time(), "s": s}
    _clean_summary_cache(cache)
    _save_summary_cache(cache)
    return s


class BlueProtocolNewsPlugin(Star):
    _GROUP_MSG_TYPE = "GroupMessage"

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._limit = _RateLimit(3)
        self._last_check: float = 0
        self._scheduler_task: asyncio.Task | None = None
        self.data_dir = _data_dir()
        screenshot.configure(self.data_dir)
        # 面板：群号 → 群名（OneBot 的群消息事件不带群名，只能自己攒）
        self.groups = GroupNameResolver(self.data_dir / "groups.json")
        self.groups.load()
        self._group_name_tasks: dict[str, asyncio.Task] = {}
        self.page = NewsPageController(context, self, data_dir=self.data_dir)
        self.page.register_routes()
        logger.info("Blue Protocol: Star Resonance announcement plugin initialized")

    # ---------------- 工具 ----------------

    @staticmethod
    def _cap(pattern: str, event: AstrMessageEvent) -> str:
        rx = _RE_CACHE.get(pattern)
        if rx is None:
            rx = _RE_CACHE[pattern] = re.compile(pattern)
        m = rx.match(event.message_str.strip())
        if not m or not m.groups():
            return ""
        return (m.group(1) or "").strip()

    @staticmethod
    def _group_key(event: AstrMessageEvent) -> str:
        try:
            return f"{event.get_platform_name()}:{event.get_session_id()}"
        except Exception:  # noqa: BLE001
            return event.unified_msg_origin

    @staticmethod
    def _group_id(event: AstrMessageEvent) -> str:
        # 优先用公开 API get_group_id()（跨平台稳定，qq_official 也认），
        # 取不到再退回 message_obj.group_id（老行为，保证不回归）。
        getter = getattr(event, "get_group_id", None)
        if callable(getter):
            try:
                gid = str(getter() or "")
                if gid:
                    return gid
            except Exception:  # noqa: BLE001
                pass
        try:
            return str(event.message_obj.group_id or "")
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _is_admin(event: AstrMessageEvent) -> bool:
        try:
            return event.is_admin()
        except Exception:  # noqa: BLE001
            return False

    def _platform_instances(self) -> list[tuple]:
        """当前已加载平台的 (实例id, 适配器类型名) 列表；取不到返回空。

        兼容两种取法：platform_manager.platform_insts / get_insts()。
        """
        for get in (
            lambda: self.context.platform_manager.platform_insts,
            lambda: self.context.get_platform_insts(),
            lambda: self.context.platform_manager.get_insts(),
        ):
            try:
                insts = list(get() or [])
            except Exception:  # noqa: BLE001
                continue
            out = []
            for p in insts:
                try:
                    meta = p.meta()
                    out.append((str(meta.id), str(meta.name)))
                except Exception:  # noqa: BLE001
                    continue
            if out:
                return out
        return []

    def _bare_id_platform(self) -> str:
        """裸群号要挂到哪个平台**实例 id** 上。

        AstrBot 的 send_message 按实例 id 匹配平台（不是适配器类型名），所以：
        配置填了就用它（是类型名时映射到同类型实例）；留空则优先 aiocqhttp 类型的实例；
        都探不到才回落 aiocqhttp（与旧行为一致）。
        """
        configured = (
            str(self.config.get("default_platform", "") or "").strip()
            if hasattr(self.config, "get")
            else ""
        )
        insts = self._platform_instances()
        ids = [pid for pid, _ in insts]
        if configured:
            if not ids or configured in ids:
                return configured
            for pid, ptype in insts:
                if ptype == configured:
                    return pid
            return configured
        for pid, ptype in insts:
            if ptype == "aiocqhttp":
                return pid
        return ids[0] if ids else "aiocqhttp"

    def _norm_umo(self, entry) -> str:
        s = str(entry or "").strip()
        if not s:
            return ""
        if ":" not in s:  # 裸群号 → 补默认平台实例 id
            return f"{self._bare_id_platform()}:{self._GROUP_MSG_TYPE}:{s}"
        # 平台段写成了适配器类型名（aiocqhttp / qq_official）时换成实例 id，否则
        # send_message 按实例 id 匹配不到、静默丢消息；认不出来的原样返回。
        parts = s.split(":")
        plat = parts[0].strip()
        insts = self._platform_instances()
        if plat and not any(plat == pid for pid, _ in insts):
            for pid, ptype in insts:
                if ptype == plat:
                    parts[0] = pid
                    return ":".join(parts)
        return s

    def _push_groups(self) -> list[str]:
        out = []
        for raw in list(self.config.get("news_groups", []) or []):
            umo = self._norm_umo(raw)
            if umo and umo not in out:
                out.append(umo)
        return out

    async def _send_text_to(self, umo: str, text: str) -> None:
        from astrbot.api.event import MessageChain

        await self.context.send_message(umo, MessageChain().message(text))

    async def _send_img_to(self, umo: str, url: str) -> None:
        from astrbot.api.event import MessageChain

        chain = MessageChain()
        if url.startswith(("http://", "https://")):
            chain.url_image(url)
        else:
            chain.file_image(url)
        await self.context.send_message(umo, chain)

    # ---------------- 面板：群名与群列表 ----------------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_any_message(self, event: AstrMessageEvent):
        """任何消息都顺手记一下群名（面板要按群名选群）。不产出任何回复。"""
        try:
            self._remember_group(event)
        except Exception as e:  # noqa: BLE001
            logger.debug("记录群名失败: %s", e)

    @staticmethod
    def _event_group_name(event: AstrMessageEvent) -> str:
        """事件自带的群名（Telegram / Discord / QQ 官方等平台有，OneBot 没有）。"""
        group = getattr(getattr(event, "message_obj", None), "group", None)
        return str(getattr(group, "group_name", "") or "").strip()

    @staticmethod
    def _event_platform_id(event: AstrMessageEvent) -> str:
        getter = getattr(event, "get_platform_id", None)
        if callable(getter):
            try:
                return str(getter() or "")
            except Exception:  # noqa: BLE001
                pass
        meta = getattr(event, "platform_meta", None)
        return str(getattr(meta, "id", "") or "")

    def _remember_group(self, event: AstrMessageEvent) -> None:
        umo = str(getattr(event, "unified_msg_origin", "") or "")
        if not umo:
            return
        gid = self._group_id(event)
        self.groups.remember(
            umo,
            group_id=gid,
            group_name=self._event_group_name(event),
            platform_id=self._event_platform_id(event),
        )
        if gid and not self.groups.name_of(umo):
            self._schedule_group_name_lookup(event, umo, gid)

    def _schedule_group_name_lookup(self, event: AstrMessageEvent, umo: str, gid: str) -> None:
        """首次见到某个群时后台问一次 get_group_info（不阻塞消息处理）。"""
        if umo in self._group_name_tasks:
            return
        client = getattr(event, "bot", None) or getattr(event, "client", None)
        if client is None or not callable(getattr(client, "call_action", None)):
            return
        try:
            task = asyncio.create_task(
                self._learn_group_name(client, umo, gid, self._event_platform_id(event))
            )
        except RuntimeError:  # 没有运行中的事件循环
            return
        self._group_name_tasks[umo] = task
        task.add_done_callback(lambda _t, key=umo: self._group_name_tasks.pop(key, None))

    async def _learn_group_name(self, client, umo: str, gid: str, platform_id: str) -> None:
        try:
            result = await client.call_action(
                "get_group_info", group_id=int(gid) if str(gid).isdigit() else gid
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("查询群 %s 名称失败: %s", gid, e)
            return
        info = parse_group_info(result)
        name = str(info.get("group_name") or "").strip()
        if not name:
            return
        self.groups.remember(
            umo,
            group_id=gid or str(info.get("group_id") or ""),
            group_name=name,
            platform_id=platform_id,
            member_count=info.get("member_count"),
            source=SOURCE_API,
        )

    @staticmethod
    def _platform_instance_id(inst) -> str:
        meta = getattr(inst, "meta", None)
        if callable(meta):
            try:
                return str(getattr(meta(), "id", "") or "")
            except Exception:  # noqa: BLE001
                pass
        config = getattr(inst, "config", None)
        if isinstance(config, dict):
            return str(config.get("id") or "")
        return ""

    def _platform_clients(self):
        """列出 (平台实例 id, 客户端对象)；取不到平台管理器时一个都不返回。"""
        manager = getattr(self.context, "platform_manager", None)
        getter = getattr(manager, "get_insts", None)
        if not callable(getter):
            return
        try:
            insts = list(getter() or [])
        except Exception as e:  # noqa: BLE001
            logger.debug("取平台实例失败: %s", e)
            return
        for inst in insts:
            client = None
            get_client = getattr(inst, "get_client", None)
            if callable(get_client):
                try:
                    client = get_client()
                except Exception:  # noqa: BLE001
                    client = None
            if client is None:
                client = getattr(inst, "bot", None) or getattr(inst, "client", None)
            if client is not None:
                yield self._platform_instance_id(inst), client

    async def refresh_group_names(self, force: bool = False, interval: int = 300) -> int:
        """去平台要一遍群列表（OneBot get_group_list）补齐群名，返回有变化的群数。"""
        if not force and not self.groups.needs_refresh(interval):
            return 0
        changed = 0
        for platform_id, client in self._platform_clients():
            action = getattr(client, "call_action", None)
            if not callable(action):
                continue
            try:
                result = await action("get_group_list")
            except Exception as e:  # noqa: BLE001
                logger.debug("平台 %s 取群列表失败: %s", platform_id or "?", e)
                continue
            changed += self.groups.merge_api_groups(platform_id, parse_group_list(result))
        self.groups.mark_refreshed()
        return changed

    async def save_config_now(self) -> None:
        """面板改完配置后落盘（同步 / 异步两套 API 都兼容）。"""
        saver = getattr(self.config, "save_config_async", None)
        if callable(saver):
            await saver()
            return
        saver = getattr(self.config, "save_config", None)
        if callable(saver):
            saver()

    # ---------------- 指令 ----------------

    @filter.regex(T_LIST)
    async def list_cmd(self, event: AstrMessageEvent):
        '''bp list [category] [page]: announcement list (category: notice/news/event/all)'''
        if not self._limit.ok(self._group_key(event)):
            yield event.plain_result("请求过于频繁，请稍后再试。")
            return
        try:
            tag_name, page = self._parse_list_args(event)
            tag_id = resolve_tag(tag_name) or TAG_ALL
            page = max(1, page)
            size = int(self.config.get("list_page_size", 10) or 10)
            items, info = await fetch_news_list(page=page, page_size=size, tag_id=tag_id)
            if not items:
                yield event.plain_result("没有找到公告。")
                return
            title = f"{GAME_NAME} — 公告列表"
            label = tag_display_name(tag_id)
            if tag_id != TAG_ALL and label:
                title += f" ({label})"
            title += f" | 第 {info.get('page', page)}/{info.get('totalpage', 1)} 页\n"
            lines = [title]
            for i, it in enumerate(items):
                tag = f"[{it['tag']}] " if it.get("tag") else ""
                lines.append(
                    f"{i + 1}. {tag}{it['title']}\n   {it['time']}\n   {it['url']}"
                )
            total = int(info.get("total", len(items)))
            if info.get("totalpage", 1) > 1:
                lines.append(
                    f"... 共 {total} 条公告，当前第 {info.get('page', page)} 页 / "
                    f"共 {info.get('totalpage', 1)} 页（每页 {info.get('pagesize', size)} 条）"
                )
            yield event.plain_result("\n\n".join(lines))
        except Exception as e:  # noqa: BLE001
            yield event.plain_result(f"获取公告失败：{e}")

    @staticmethod
    def _parse_list_args(event: AstrMessageEvent) -> tuple[str, int]:
        """从「bp list notice 2」里拆出 (分类, 页码)。"""
        rx = _RE_CACHE.get(T_LIST) or re.compile(T_LIST)
        m = rx.match(event.message_str.strip())
        tag_name = ""
        page = 1
        if m:
            if m.group(1):
                tag_name = m.group(1)
            if m.group(2):
                try:
                    page = int(m.group(2))
                except ValueError:
                    page = 1
        return tag_name, page

    @filter.regex(T_LATEST)
    async def latest_cmd(self, event: AstrMessageEvent):
        '''bp latest: the newest announcement — summary text + phone-sized long image'''
        if not self._limit.ok(self._group_key(event)):
            yield event.plain_result("请求过于频繁，请稍后再试。")
            return
        for r in await self._latest(event, force=True):
            yield r

    @filter.regex(T_LATEST_DEDUP)
    async def latest_dedup_cmd(self, event: AstrMessageEvent):
        '''bp latest dedup: only replies when there is a new announcement (per-group dedup)'''
        if not self._limit.ok(self._group_key(event)):
            yield event.plain_result("请求过于频繁，请稍后再试。")
            return
        for r in await self._latest(event, force=False):
            yield r

    @filter.regex(T_HELP)
    async def help_cmd(self, event: AstrMessageEvent):
        '''bp help: command usage'''
        p = _PREFIX_TEXT
        yield event.plain_result(
            f"{GAME_NAME} 公告机器人\n\n"
            f"{p} list [分类] [页码]\n"
            f"    公告列表\n"
            f"    分类：all | notice | news | event   （默认 all）\n"
            f"    页码：从 1 开始（默认 1）\n\n"
            f"{p} latest\n"
            f"    最新公告 —— 摘要文字 + 手机长图\n\n"
            f"{p} latest dedup\n"
            f"    最新公告，只有出新公告时才回复\n\n"
            f"{p} push on | off | status | test\n"
            f"    本群自动推送，每 5 分钟检查一次（on / off / test 需要管理员）\n\n"
            f"{p} reset\n"
            f"    清空本群的公告推送记录（需要管理员）\n\n"
            f"前缀别名：bp / blue protocol / blueprotocol\n\n"
            f"—— English ——\n"
            f"{p} list [category] [page]\n"
            f"    announcement list\n"
            f"    category: all | notice | news | event   (default: all)\n"
            f"    page: page number (default: 1)\n\n"
            f"{p} latest\n"
            f"    newest announcement — summary text + long image\n\n"
            f"{p} latest dedup\n"
            f"    newest announcement, only when there is something new\n\n"
            f"{p} push on | off | status | test\n"
            f"    auto-push for this group (on / off / test need admin)\n\n"
            f"{p} reset\n"
            f"    clear this group's push record (admin)\n\n"
            f"Prefix aliases: bp / blue protocol / blueprotocol"
        )

    async def _latest(self, event: AstrMessageEvent, force: bool) -> list:
        key = self._group_id(event) or f"session:{event.unified_msg_origin}"
        results = []
        try:
            items, _ = await fetch_news_list(page=1, page_size=5)
            if not items:
                if force:
                    results.append(event.plain_result("没有找到公告。"))
                return results
            it = items[0]
            if not force and last_pushed(key) == it["title"]:
                return results
            mark_pushed(key, it["title"])
            detail = await self._detail_of(it)
            summary = await fetch_summary_cached(detail)
            text = self._news_text(it, summary)
            img, hint = await self._news_image(it, detail, summary)
            results.append(event.plain_result(text + hint))
            if img:
                results.append(event.image_result(img))
        except Exception as e:  # noqa: BLE001
            logger.warning("latest announcement fetch failed: %s", e)
            if force:
                results.append(event.plain_result(f"获取公告失败：{e}"))
        return results

    @staticmethod
    async def _detail_of(item: dict) -> dict:
        """取公告详情；失败时退回列表项（至少还能出标题/时间）。"""
        news_id = str(item.get("news_id") or "")
        if not news_id:
            return {}
        try:
            return await fetch_detail(news_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("announcement detail fetch failed %s: %s", news_id, e)
            return dict(item)

    @staticmethod
    def _news_text(it: dict, summary: str) -> str:
        tag = f"分类：{it['tag']}\n" if it.get("tag") else ""
        text = (
            f"最新公告：\n\n{tag}标题：{it['title']}\n"
            f"时间：{it['time']}\n链接：{it['url']}"
        )
        if summary:
            text += f"\n\n{summary}"
        return text

    @filter.regex(T_PUSH)
    async def push_cmd(self, event: AstrMessageEvent):
        '''bp push on|off|status|test: toggle auto-push for this group (checked every 5 minutes)'''
        arg = self._cap(T_PUSH, event)
        if not self._group_id(event):
            yield event.plain_result("该指令只能在群聊中使用。")
            return
        groups = list(self.config.get("news_groups", []) or [])
        umo = self._norm_umo(self._umo_of(event))
        if arg == "on":
            if not self._is_admin(event):
                yield event.plain_result("需要管理员权限。")
                return
            if umo not in groups:
                groups.append(umo)
            self.config["news_groups"] = groups
            await self.save_config_now()
            yield event.plain_result(
                f"本群已开启自动推送"
                f"（{GAME_NAME} 公告，每 5 分钟检查一次）。"
            )
        elif arg == "off":
            if not self._is_admin(event):
                yield event.plain_result("需要管理员权限。")
                return
            self.config["news_groups"] = [g for g in groups if g != umo]
            await self.save_config_now()
            yield event.plain_result("本群已关闭自动推送。")
        elif arg == "status":
            on = umo in groups
            yield event.plain_result(
                f"本群自动推送：{'开启（每 5 分钟检查一次）' if on else '关闭'}\n"
                "开启后，机器人会自动把新公告推送到群里。"
            )
        elif arg == "test":
            if not self._is_admin(event):
                yield event.plain_result("需要管理员权限。")
                return
            for r in await self._latest(event, force=True):
                yield r
        else:
            yield event.plain_result(
                f"用法：{_PREFIX_TEXT} push on | off | status | test"
            )

    def _umo_of(self, event: AstrMessageEvent) -> str:
        return event.unified_msg_origin

    @filter.regex(T_RESET)
    async def reset_cmd(self, event: AstrMessageEvent):
        '''bp reset: clear this group's push record (admin only)'''
        if not self._group_id(event):
            yield event.plain_result("该指令只能在群聊中使用。")
            return
        if not self._is_admin(event):
            yield event.plain_result("需要管理员权限。")
            return
        key = self._group_id(event)
        clear_pushed(key)
        yield event.plain_result("本群的公告推送记录已清空。")

    # ---------------- 公告长图（Typst 本地排版优先，失败逐级回退） ----------------

    def _typst_options(self) -> dict:
        """Typst 排版相关配置。"""
        return {
            "ppi": int(self.config.get("typst_ppi", typst_render.DEFAULT_PPI) or 144),
            "timeout": float(
                self.config.get("typst_timeout", typst_render.DEFAULT_TIMEOUT) or 60
            ),
            "font_url": str(self.config.get("typst_font_url", "") or "") or None,
        }

    def _long_image_options(self) -> dict:
        """长图版式配置（画布宽度/正文宽度/边框/主题/段间距/行高）。"""
        return {
            "width": int(
                self.config.get("typst_long_width", layout.DEFAULT_WIDTH)
                or layout.DEFAULT_WIDTH
            ),
            "body_width": int(
                self.config.get("typst_long_body_width", layout.DEFAULT_BODY_WIDTH)
                or 0
            ),
            "border": int(
                self.config.get("typst_long_border", layout.DEFAULT_BORDER)
                or 0
            ),
            "theme": str(self.config.get("typst_long_theme", layout.DEFAULT_THEME) or ""),
            "para_spacing": float(
                self.config.get("typst_para_spacing", layout.DEFAULT_PARA_SPACING)
                or 0
            ),
            "line_height": float(
                self.config.get("typst_line_height", layout.DEFAULT_LINE_HEIGHT)
                or layout.DEFAULT_LINE_HEIGHT
            ),
        }

    async def _news_image(
        self, it: dict, detail: dict, summary: str
    ) -> tuple[str | None, str]:
        """返回 (图片路径/URL, 追加到文字消息的提示)。

        渲染顺序：
          ① Typst 本地排版的长图（首选，不依赖浏览器组件）；
          ② Playwright 整页截图长图（Typst 不可用时的兜底）；
          ③ Typst 排版的卡片；
          ④ html_render 卡片（最后兜底）。
        """
        note = ""
        use_typst = bool(self.config.get("typst_enabled", True))
        options = self._typst_options()
        long_options = self._long_image_options()

        if use_typst:
            try:
                path, truncated = await typst_render.render_long_image(
                    detail or it,
                    self.data_dir,
                    ppi=options["ppi"],
                    timeout=options["timeout"],
                    max_height=int(
                        self.config.get("shot_max_height", screenshot.MAX_HEIGHT)
                    ),
                    quality=int(self.config.get("shot_quality", screenshot.JPEG_QUALITY)),
                    font_url=options["font_url"],
                    **long_options,
                )
                if truncated:
                    note = "\n\n（这条公告比较长，图片只显示前半部分，完整内容请点链接查看。）"
                return str(path), note
            except Exception as e:  # noqa: BLE001
                logger.warning("Typst 长图排版失败，回退到浏览器渲染：%s", e)

        if self.config.get("shot_enabled", True):
            try:
                html = render_article(detail or it, **long_options)
                path, truncated = await screenshot.shot_article(
                    html,
                    str(it.get("news_id") or it.get("url") or it.get("title")),
                    max_height=int(
                        self.config.get("shot_max_height", screenshot.MAX_HEIGHT)
                    ),
                    quality=int(self.config.get("shot_quality", screenshot.JPEG_QUALITY)),
                    width=long_options["width"],
                )
                screenshot.clean_shots()
                if truncated:
                    note = "\n\n（这条公告比较长，图片只显示前半部分，完整内容请点链接查看。）"
                return path, note
            except RuntimeError as e:
                if str(e) == "DOWNLOADING":
                    logger.info("browser component is downloading, falling back to the card image")
                    note = "\n\n（浏览器组件正在后台下载，准备好之后就会改用长图。）"
                else:
                    logger.warning("announcement long image render failed: %s", e)
            except Exception as e:  # noqa: BLE001
                logger.warning("announcement long image render failed: %s", e)

        if use_typst:
            try:
                path = await typst_render.render_card(
                    it,
                    summary,
                    self.data_dir,
                    ppi=options["ppi"],
                    timeout=options["timeout"],
                    quality=int(self.config.get("shot_quality", screenshot.JPEG_QUALITY)),
                    font_url=options["font_url"],
                )
                return str(path), note
            except Exception as e:  # noqa: BLE001
                logger.warning("Typst 卡片排版失败，回退到 html_render：%s", e)

        try:
            return await self._render_card(it, summary), note
        except Exception as e:  # noqa: BLE001
            logger.warning("announcement card render failed: %s", e)
            return None, note

    # ---------------- 公告卡片（html_render 渲染，深色风格，截图不可用时的兜底） ----------------

    @staticmethod
    def _measure_wrap_lines(
        text: str, content_px: float, font_px: float, ascii_ratio: float = 0.55
    ) -> int:
        """按 CSS 像素估算折行后的总行数（CJK 一字≈font_px，ASCII≈font_px*0.55）。"""
        if not text:
            return 0
        import math

        lines = 0
        for para in str(text).split("\n"):
            w = 0.0
            for ch in para:
                w += font_px if ord(ch) > 127 else font_px * ascii_ratio
            lines += max(1, math.ceil(w / content_px))
        return lines

    def _card_clip(self, it: dict, summary: str) -> dict:
        """估算卡片内容高度并构造 clip（t2i 端点固定输出 800x720，需按内容裁剪）。

        与 templates/card.html 版式逐项对应：
        brand 72 + content pad 26 + tag 24 + title(margin12+行40.6) + meta(10+18)
        + desc(margin18+行30.4) + divider 21 + link(18+24+行20.8) + foot 33
        + page pad 18。
        底部留 20px 余量（现在是 KV 底图，多留一点也只是多露一点背景），
        宁多勿少防切字。
        """
        title_lines = self._measure_wrap_lines(it.get("title", ""), 736, 28)
        link_lines = self._measure_wrap_lines(
            f"原文链接：{it.get('url', '')}", 672, 13
        )
        h = 72 + 26 + 24 + 12 + title_lines * 40.6 + 10 + 18 + 21
        h += 18 + 24 + link_lines * 20.8 + 33 + 18
        if summary:
            desc_lines = self._measure_wrap_lines(summary, 736, 16)
            h += 18 + desc_lines * 30.4
        return {"x": 0, "y": 0, "width": 800, "height": min(int(h) + 20, 720)}

    async def _render_card(self, it: dict, summary: str) -> str:
        """渲染公告卡片图片（深色风格），返回图片 URL。"""
        from bpnews.render import CARD_TEMPLATE

        if not CARD_TEMPLATE.is_file():
            raise RuntimeError(
                f"template missing: {CARD_TEMPLATE}. The plugin folder is incomplete, please reinstall the full zip"
            )
        return await self.html_render(
            CARD_TEMPLATE.read_text(encoding="utf-8"),
            card_data(it, summary),
            options={"type": "png", "clip": self._card_clip(it, summary)},
        )

    # ---------------- 定时推送 ----------------

    @filter.on_astrbot_loaded()
    async def on_astrbot_loaded(self):
        if self._scheduler_task is None:
            self._scheduler_task = asyncio.create_task(self._scheduler())

    async def _scheduler(self):
        while True:
            try:
                await self._tick()
            except Exception as e:  # noqa: BLE001
                logger.warning("scheduler error: %s", e)
            await asyncio.sleep(30)

    async def _tick(self):
        if not self._push_groups() or time.time() - self._last_check < 300:
            return
        self._last_check = time.time()
        await self._push_round()

    async def _push_round(self, target: str | None = None, force: bool = False) -> dict:
        """跑一轮推送：面板「立刻检查并推送」与定时任务共用同一段逻辑。

        target 指定只推一个群；force=True 忽略去重记录重发（面板「测试推送」用）。
        返回 {reason, title, pushed, skipped, message}，pushed/skipped 是 umo 列表。
        """
        if target:
            groups = [self._norm_umo(target)]
        else:
            groups = self._push_groups()
        groups = [u for u in groups if u]
        if not groups:
            return {
                "reason": "no_groups",
                "title": "",
                "pushed": [],
                "skipped": [],
                "message": "No push targets yet — pick groups in the panel, or send \"bp push on\" in a group.",
            }
        try:
            items, _ = await fetch_news_list(page=1, page_size=5)
            if not items:
                return {
                    "reason": "no_list",
                    "title": "",
                    "pushed": [],
                    "skipped": [],
                    "message": "The announcement list came back empty (the data source returned nothing).",
                }
            it = items[0]
        except Exception as e:  # noqa: BLE001
            logger.warning("scheduled announcement list fetch failed: %s", e)
            return {
                "reason": "fetch_failed",
                "title": "",
                "pushed": [],
                "skipped": [],
                "message": f"Failed to fetch the announcement list: {e}",
            }

        need = (
            groups
            if force
            else [umo for umo in groups if last_pushed(f"push:{umo}") != it["title"]]
        )
        skipped = [umo for umo in groups if umo not in need]
        if not need:
            return {
                "reason": "up_to_date",
                "title": it["title"],
                "pushed": [],
                "skipped": skipped,
                "message": f"The latest announcement was already pushed: {it['title']}",
            }

        # 摘要/长图只生成一次（内部有缓存，多群共用同一文件）
        detail = await self._detail_of(it)
        summary = await fetch_summary_cached(detail)
        text = self._news_text(it, summary)
        img, hint = await self._news_image(it, detail, summary)
        text += hint
        pushed: list[str] = []
        for umo in need:
            try:
                mark_pushed(f"push:{umo}", it["title"])
                await self._send_text_to(umo, text)
                if img:
                    await self._send_img_to(umo, img)
                pushed.append(umo)
            except Exception as e:  # noqa: BLE001
                logger.warning("scheduled push failed for %s: %s", umo, e)
        message = f"Pushed \"{it['title']}\" to {len(pushed)} group(s)"
        if skipped:
            message += f", {len(skipped)} group(s) already up to date (skipped)"
        return {
            "reason": "ok",
            "title": it["title"],
            "pushed": pushed,
            "skipped": skipped,
            "message": message,
        }

    async def push_now(self, target: str | None = None, *, force: bool = False) -> dict:
        """面板「立刻检查并推送」：忽略 5 分钟节流跑一轮。"""
        self._last_check = time.time()
        return await self._push_round(target, force=force)

    async def terminate(self):
        if self._scheduler_task:
            self._scheduler_task.cancel()
