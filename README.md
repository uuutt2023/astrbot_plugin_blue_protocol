# astrbot_plugin_blue_protocol

**Blue Protocol: Star Resonance** (《蓝色协议：星痕共鸣》) official announcement bot for AstrBot.
《蓝色协议：星痕共鸣》官方公告推送插件 —— 公告列表、最新公告长图、按群去重、定时推送，带 Web 面板。

Announcement list with paging and categories, latest announcement with a summary and a browser-width long image, per-group deduplication, scheduled auto-push, plus a web panel for managing push targets by group name.

公告列表支持分页与分类；最新公告带正文摘要与浏览器宽度长图；按群去重；每 5 分钟检查一次自动推送；Web 面板可按群名管理推送群、手动推送、查看长图缓存。

Data comes from the Tencent game announcement API behind the official site (`apps.game.qq.com/wmp/v3.1/`) — both the list and the article body are served straight from the API, no HTML scraping.

数据来自官网背后的腾讯游戏公告接口（`apps.game.qq.com/wmp/v3.1/`），列表与正文都直接取自接口，不抓取 HTML。

---

# English

## Typesetting with Typst

Announcement images are typeset **locally with [Typst](https://typst.app/)** — no browser component needed:

- The long image and the card are compiled by the `typst` Python package inside an **isolated subprocess** with a timeout and a hard kill, so a weird announcement can never wedge the plugin.
- The announcement HTML is turned into a tiny JSON contract (`runs` / `br`); the templates live in `templates/typst/*.typ` and are compiled against `data.json`.
- The CJK font is resolved from the plugin data directory first, then from system fonts, and finally downloaded once on first use. The resolved family name is passed to the template, so no “unknown font family” warnings.
- Typst is the **primary** renderer. If it is missing or fails, the plugin falls back to the Playwright long image, then to the Typst card, and finally to the `html_render` card — images keep working either way.

The layout is measured in **CSS pixels**, just like in a browser:

| What | Default | Config key |
|---|---|---|
| Canvas width | `1280` px (a typical browser width) | `typst_long_width` |
| Text column width | `1258` px | `typst_long_body_width` |
| Border on both sides of the column | `11` px | `typst_long_border` |
| Theme | `dark` (or `light`) | `typst_long_theme` |
| Paragraph spacing | `14` px | `typst_para_spacing` |
| Line height | `1.8` | `typst_line_height` |
| Module spacing | `34` px | `typst_module_spacing` |

Both renderers share one layout definition (`bpnews/layout.py`), so the Typst image and the Playwright fallback come out looking the same.

### Modules

Announcements are written as a series of modules, so the long image keeps that structure instead of running everything together:

- **Module headings** are detected three ways — an explicit `<h2>`/`<h3>` tag, a whole line wrapped in `<strong>`, or a short standalone line (`以下为本次更新内容详情：`, `1. 扭蛋活动轮换`). Top-level modules get a gold bar on the left; sub-modules are bold.
- **Module spacing** (`typst_module_spacing`, default `34` px) is the blank space above a module heading — raise it for a roomier page, lower it for a denser one.
- **Inline images** in the body are kept and scaled to the text column (small images are not blown up).
- **Inline colours** from the official page are dropped, so text stays readable on both the dark and the light theme.

## Announcement long image

The announcement body is returned as HTML by the API, so the plugin renders it through its own template — the content is complete, and it does not depend on the official site's JavaScript-rendered SPA. The canvas defaults to a full browser width, so the body text is as wide as a desktop page.

![Announcement long image preview](docs/images/news-longimage-preview.jpg)

## Announcement card

When the long image cannot be rendered (Playwright unavailable), the plugin falls back to a share card built on the **official KV banner** (`game.gtimg.cn/images/bpm/web202412/kv.jpg`):

- The banner fills the whole card **PPT style** — full bleed, `background-size: cover`.
- A diagonal gradient scrim runs from **0 % opacity at the top-left to 100 % at the bottom-right**, and the banner itself is dimmed (`brightness(.58)`), so the title, summary and link stay readable.
- The top-left corner reuses the official `.news-container::before / ::after` technique (`news-detail-bg.jpg`) to draw the accent divider line, masked so it fades out towards the right.

![Announcement card preview](docs/images/news-card-preview.jpg)

## Web panel preview

Toggle **light / dark** in the top right, or pick "Follow AstrBot" under *Appearance*; light is the default when the host theme is unavailable. The theme and compact-layout preference are stored in the current browser, the layout adapts on narrow screens, and wide tables scroll horizontally.

- Navigation: Overview, Push targets, Push records, Image settings, Commands, Image cache, Appearance.
- Stat cards keep their label/value rows aligned, as do the checkboxes and filter toolbar.
- Plain local HTML / CSS / JavaScript — no build step and no external icon fonts; it talks to the backend through the AstrBot Plugin Pages bridge.

**Light**

![Web panel light](docs/images/web-panel-light.png)

<details>
<summary>Dark</summary>

![Web panel dark](docs/images/web-panel-dark.png)

</details>

> Preview screenshots come from a local browser test with mock data and do not represent a live bot.

## Commands

Commands are English and start with `bp`. The aliases `blue protocol` and `blueprotocol` also work, so the prefix never collides with another plugin's bare-word commands.

**The prefixes are configurable** — set `command_prefixes` in the plugin config, or edit them in the panel under *Commands*. Several prefixes are allowed, spaces inside a prefix are optional, and changes apply immediately without restarting the plugin.

| Command | Description |
|---|---|
| `bp list [category] [page]` | Announcement list. Category: `all` / `notice` / `news` / `event` (default `all`). Page defaults to 1; rows per page come from `list_page_size` |
| `bp latest` | Newest announcement: category, title, date, link, summary — plus the long image |
| `bp latest dedup` | Same, but only replies when there is something new (per-group dedup) |
| `bp push on\|off\|status\|test` | Auto-push for this group, checked every **5 minutes** (`on` / `off` / `test` need admin) |
| `bp reset` | Clear this group's push record (admin) |
| `bp help` | Command usage |

Examples:

```
bp list
bp list notice 2
blueprotocol list news
bp push on
bp latest
```

Category aliases: `notice` = `announcement` / `announcements` / `ann`, `event` = `events` / `activity`, `all` = `latest`. Matching is case-insensitive.

A message whose prefix is not in the configured list is left alone — it goes to the LLM as usual instead of being swallowed by this plugin.

## Internationalisation

The plugin ships two languages, English and 中文 (Simplified Chinese).

| Where | How the language is chosen |
|---|---|
| **Web panel UI** | Auto-detected from the **browser time zone**: China mainland / Hong Kong / Macau / Taiwan → 中文, everywhere else → English. The top-right button (and the *Language* select under *Appearance*) switches it manually; your choice is remembered in this browser and always wins over auto-detection. |
| **Plugin config page** (AstrBot WebUI) | Follows AstrBot's own interface language. Both `zh-CN` and `en-US` are provided. |
| **Plugin marketplace entry** | Follows AstrBot's own interface language. |

The announcement titles and bodies themselves stay in the game's original Chinese — only the plugin's own interface is translated.

## Configuration (WebUI plugin config page)

| Key | Default | Description |
|---|---|---|
| `command_prefixes` | `["bp", "blue protocol"]` | Words that trigger the bot in chat. Several are allowed and spaces are optional (`blueprotocol` works too). Changes apply immediately |
| `news_groups` | `[]` | Groups that receive scheduled pushes (a **group id** or `unified_msg_origin`, multiple allowed). You can also send `bp push on` in a group, or **tick groups by name in the plugin panel** |
| `list_page_size` | `10` | Announcements per page in `bp list` (1-30) |
| `shot_enabled` | `true` | Render announcements as a long image; when off it falls back to the dark card image |
| `shot_max_height` | `5000` | Maximum long-image height in CSS pixels (0 = no limit). Very long announcements are cut here and the text message points to the link |
| `shot_quality` | `88` | Long-image JPEG quality. Images above 2.5 MB are downscaled automatically |
| `typst_enabled` | `true` | Typeset announcement images with the local Typst compiler (primary renderer); when off the plugin uses browser screenshots |
| `typst_ppi` | `144` | Typst export density in PPI (72-300). Higher means sharper and larger |
| `typst_timeout` | `60` | Time limit for one Typst run in seconds (5-600). On timeout the compile process is killed |
| `typst_font_url` | `""` | Optional CJK font download URL, used when the system has no Chinese font |
| `typst_long_width` | `1280` | Long-image canvas width in pixels (a typical browser width) |
| `typst_long_body_width` | `1258` | Text column width in pixels; `0` follows the canvas width minus the borders |
| `typst_long_border` | `11` | Border on both sides of the text column, in pixels |
| `typst_long_theme` | `dark` | Long-image theme: `dark` or `light` (the share card always stays dark) |
| `typst_para_spacing` | `14` | Paragraph spacing in pixels |
| `typst_line_height` | `1.8` | Line height multiplier |
| `typst_module_spacing` | `34` | Blank space above a module heading, in pixels |

## Web panel (the recommended way to manage push targets)

AstrBot WebUI → Plugins → Blue Protocol: Star Resonance → open the panel (needs AstrBot ≥ 4.24.1):

- **Commands** — change the words that trigger the bot (several are allowed), with a quick reference of every command below.
- **Push targets** — tick groups by **name** (the dropdown shows `group name (group id)`), so you never have to remember an id. `Select groups…` searches by name or id, and `Refresh group list` pulls every group the bot is in at once.
- **Check & push now** — run a round immediately instead of waiting for the 5-minute poll. Per-group `Test push` can force a re-send to verify delivery.
- **Push records** — the last announcement pushed to each group, with per-group or global reset.
- **Image cache** — thumbnails of the rendered long images plus their disk usage, with a one-click clear. The image settings (on/off, max height, quality) are editable here too.
- The selection in `Select groups…` only applies after you press **Save push targets** — it writes back the same `news_groups` config as `bp push on` does in a group.

> When you type a **bare group id**, the plugin expands it to `platform instance id` + `GroupMessage` + id (e.g. `napcat:GroupMessage:123`). Use the *instance id*, not the adapter type name: AstrBot's `send_message` matches on the instance id, so `aiocqhttp:GroupMessage:123` is silently dropped.

Group names are collected as messages arrive (platform events that carry a name are used directly); the first time a group is seen the plugin asks the platform for `get_group_info` in the background, and `Refresh group list` calls `get_group_list` once to fill in every group — so **groups that have never spoken are selectable too**. The cache lives in `groups.json`; a group with no cached name shows as `群 <id>`, which does not affect delivery.

## Data files

All under `data/plugin_data/astrbot_plugin_blue_protocol/`:

- `push_record.json` — per-group push dedup records
- `summary_cache.json` — summary cache (24 h)
- `news_shots/` — rendered long images, keyed by announcement id (newest 20 kept, plus a 7-day fallback)
- `groups.json` — group name cache for the panel (safe to delete; the panel just falls back to group ids)

## Implementation notes

- **Endpoints**
  - List: `https://apps.game.qq.com/wmp/v3.1/?p0=440&p1=searchNewsKeywordsList&page=<page>&pagesize=<size>&order=sIdxTime&r0=script&r1=NewsObj5014741213624121&type=iTag&id=<category id>&source=web_pc`
  - Detail: `https://apps.game.qq.com/wmp/v3.1/public/searchNews.php?p0=440&source=web_pc&id=<news id>`
  - Human-readable article: `https://gm.qq.com/web202503/news-detail.html?newsid=<news id>`
- **JSONP, not JSON** — both endpoints answer with `var XXX = {...};`. The plugin strips the wrapper with a brace-matching scan that is aware of string escapes; a regex breaks on the escaped braces inside `sCoverMap`.
- **The payload lives in `msg`** — the `data` field is an empty string and `status: 0` means success.
- **Category ids are hard-coded** in the official `news-list.html` (`newsTagList`): `136243=all`, `136246=notice`, `136245=news`, `136247=event`. The list endpoint filters with `type=iTag&id=<id>`; `136243` is the aggregated feed, and each row's own `sTagIds` carries the real category (sometimes several, comma separated).
- **Cover images are protocol-relative** (`//static.gametalk.qq.com/...`) — `https:` is prepended before use.
- **Article body** (`msg.sContent`) is clean HTML (`<p>` / `<br/>` plus HTML entities) with no images, which makes it ideal for rendering our own long image.
- The body usually opens with "冒险者，您好！" — the summary skips that greeting line.
- Admin commands (`on` / `off` / `test` / `reset`) require AstrBot's `admins_id` (a WebUI setting, not the QQ group admin list).

## Development

```bash
python tests/test_api.py              # data layer: JSONP, field mapping, summaries
python tests/test_groups.py            # group-name cache logic
python tests/test_panel.py             # panel backend routes (astrbot is stubbed)
python tests/test_blueprotocol_main.py # main.py wiring and push flow
python tests/test_metadata.py          # packaging contract (metadata / conf schema / i18n)
python tests/test_panel_layout_ui.py   # panel UI in a real browser (needs Playwright)
python tests/test_typst_render.py      # local Typst typesetting (needs the typst package)
python tests/test_layout.py            # long-image layout shared by both renderers
python tools/make_logo.py              # regenerate logo.png / the panel icon
```

---

# 中文

## 用 Typst 本地排版

公告图现在由 **[Typst](https://typst.app/) 在本地排版**，不再依赖浏览器组件：

- 长图和卡片都由 `typst` 这个 Python 包在**独立子进程**里编译，带超时和强制结束，异常公告不会把插件卡住。
- 正文 HTML 先转成一份很小的 JSON 契约（`runs` / `br`），模板放在 `templates/typst/*.typ`，编译时读 `data.json`。
- 中文字体按「插件数据目录 → 系统字体 → 首次使用时自动下载」的顺序解析；解析出的字体名会写进数据里传给模板，不会再出现“unknown font family”警告。
- Typst 是**首选**渲染方式；装不上或出错时会依次回退到浏览器长图 → Typst 卡片 → `html_render` 卡片，图片照样能出。

版式尺寸全部按 **CSS 像素**算，和浏览器一致：

| 项目 | 默认 | 配置项 |
|---|---|---|
| 画布宽度 | `1280` px（常见浏览器宽度） | `typst_long_width` |
| 正文栏宽度 | `1258` px | `typst_long_body_width` |
| 正文两侧边框 | `11` px | `typst_long_border` |
| 主题 | `dark`（可切 `light`） | `typst_long_theme` |
| 段落间距 | `14` px | `typst_para_spacing` |
| 行高 | `1.8` | `typst_line_height` |
| 模块间距 | `34` px | `typst_module_spacing` |

Typst 与浏览器兜底共用同一份版式定义（`bpnews/layout.py`），两条路出来的图长得一样。

### 模块

公告正文本来就是分模块写的，长图保留这个结构，不再把内容糊成一坨：

- **模块标题**有三种认法 —— 显式的 `<h2>`/`<h3>` 标签、整行加粗的 `<strong>`、靠 `<br/>` 分行的短标题行（「以下为本次更新内容详情：」「1. 扭蛋活动轮换」）。一级模块左侧带金色竖条，小模块加粗。
- **模块间距**（`typst_module_spacing`，默认 `34` px）是模块标题上方的留白，想更清爽就调大，想更紧凑就调小。
- **正文内嵌图**会保留下来并按正文栏宽度缩放（太小的图不会被放大）。
- 官网正文的**行内颜色会被丢掉**，深色浅色主题下文字都读得清。

## 公告长图

公告正文由接口直接给 HTML，插件套进自带模板后整页排版 —— 内容完整、不依赖官网那个 JS 渲染的 SPA。画布默认是完整浏览器宽度，正文和网页正文一样宽。

![公告长图预览](docs/images/news-longimage-preview.jpg)

## 公告卡片

长图渲染不出来时（Playwright 不可用），插件会退回一张用**官方 KV banner**（`game.gtimg.cn/images/bpm/web202412/kv.jpg`）做的分享卡片：

- 底图铺满整张卡片，走 **PPT 样式**：`background-size: cover`，整块画面铺满。
- 斜向渐变滤镜从**左上角 0% 透明 → 右下角 100% 不透明**，同时把底图压暗（`brightness(.58)`），标题、摘要、链接都能看清。
- 左上角复用官网 `.news-container::before / ::after` 的做法（`news-detail-bg.jpg`）画出蓝色分隔线，用遮罩让它往右淡出。

![公告卡片预览](docs/images/news-card-preview.jpg)

## Web 面板

右上角可一键切换 **浅色 / 深色**，也可在「界面外观」中选择跟随 AstrBot；未提供宿主主题时默认浅色。主题及紧凑布局偏好保存在当前浏览器，手机窄屏下自动调整布局，宽表格可横向滚动。

- 页面导航：总览、推送群、推送记录、公告图设置、指令、截图缓存、界面外观。
- 统一统计卡片标签与数值排版、复选框及筛选工具栏对齐。
- 使用本地 HTML / CSS / JavaScript，无需前端构建或外部图标字体；通过 AstrBot Plugin Pages 桥接访问后端。

## 指令

指令为英文，以 `bp` 开头；`blue protocol`、`blueprotocol` 同样可用，避免与其它插件的裸词指令冲突。

| 指令 | 说明 |
|---|---|
| `bp list [分类] [页码]` | 公告列表。分类可选 `all` / `notice` / `news` / `event`（默认 `all`），页码从 1 开始，每页条数由 `list_page_size` 控制 |
| `bp latest` | 最新公告：分类/标题/日期/链接/摘要 + 长图 |
| `bp latest dedup` | 同上，但只有出新公告才回复（按群去重） |
| `bp push on\|off\|status\|test` | 本群自动推送，每 **5 分钟** 检查一次（`on` / `off` / `test` 需管理员） |
| `bp reset` | 清空本群推送记录（需管理员） |
| `bp help` | 查看指令用法 |

分类别名：`notice` = `announcement` / `announcements` / `ann`，`event` = `events` / `activity`，`all` = `latest`，不区分大小写。

## 国际化

插件内置 **English** 与 **中文（简体）** 两套语言。

| 位置 | 语言如何决定 |
|---|---|
| **Web 面板界面** | 按**浏览器时区**自动判断：中国大陆 / 港澳台 → 中文，其他地区 → English。右上角的按钮（以及「界面外观」里的 *Language* 下拉）可手动切换，选择会记在这个浏览器里，且优先级高于自动判断。 |
| **插件配置页**（AstrBot WebUI） | 跟随 AstrBot 自身的界面语言，提供 `zh-CN` 与 `en-US` 两套。 |
| **插件市场条目** | 跟随 AstrBot 自身的界面语言。 |

公告标题与正文保持游戏原样的中文，只翻译插件自己的界面。

## 配置项

| 配置项 | 默认 | 说明 |
|---|---|---|
| `command_prefixes` | `["bp", "blue protocol"]` | 在聊天里触发机器人的关键词。可以填多个，前缀里的空格可省略（`blueprotocol` 也认）。改完立刻生效 |
| `news_groups` | `[]` | 定时推送的群（填**群号**或 unified_msg_origin，可多个）。也可以在群里发 `bp push on` 自动登记本群，**或直接在插件面板里按群名勾选** |
| `list_page_size` | `10` | 公告列表每页条数（1-30） |
| `shot_enabled` | `true` | 公告图用整页长图；关掉则回到深色卡片图 |
| `shot_max_height` | `5000` | 长图最大高度（CSS 像素，0 = 不截断）。超长公告截取前面部分，文字消息里提示看链接 |
| `shot_quality` | `88` | 长图 JPEG 质量。成图超过 2.5MB 会自动继续降质/缩放 |
| `typst_enabled` | `true` | 用本地 Typst 编译器排版公告图（首选渲染方式）；关掉则改用浏览器截图 |
| `typst_ppi` | `144` | Typst 导出密度（PPI，72-300）。越高越清晰，体积也越大 |
| `typst_timeout` | `60` | 单次 Typst 排版的超时秒数（5-600）。超时会终止编译进程 |
| `typst_font_url` | `""` | 中文字体下载地址（可选），系统没有中文字体时才会用到 |
| `typst_long_width` | `1280` | 长图画布宽度（像素），默认取常见浏览器宽度 |
| `typst_long_body_width` | `1258` | 正文栏宽度（像素）；填 0 表示自动跟随画布宽度减去两侧边框 |
| `typst_long_border` | `11` | 正文栏左右两侧的边框宽度（像素） |
| `typst_long_theme` | `dark` | 长图主题：`dark` 深色 / `light` 浅色（分享卡片始终是深色） |
| `typst_para_spacing` | `14` | 段落间距（像素） |
| `typst_line_height` | `1.8` | 行高（倍数） |
| `typst_module_spacing` | `34` | 模块标题上方的留白（像素） |

## Web 面板用法

AstrBot WebUI → 插件 → Blue Protocol: Star Resonance → 打开面板（需要 AstrBot ≥ 4.24.1）：

- **指令**：改机器人的指令前缀（可填多个），下面还有一张指令速查表。
- **推送群**：按**群名**勾选要推送的群，不用记群号；`选择群…` 里可以搜索群名或群号，还能「刷新群列表」把机器人所在的全部群一次拉出来。
- **立刻检查并推送**：不用等 5 分钟轮询周期；单群「测试推送」还能强制重发，用来验证群里到底收不收得到。
- **推送记录**：每个群上次推的公告标题，支持单群/全部重置。
- **截图缓存**：公告长图缩略图 + 占用空间，一键清空；长图参数（开关/最大高度/质量）、Typst 开关，以及长图的主题/画布宽度/正文栏宽度/边框宽度/段间距/行高都能在面板里改，面板还会显示当前用的是哪套中文字体。

> 群名单里填**裸群号**时，插件会把它补成「平台**实例 id** + GroupMessage + 群号」（例如 `napcat:GroupMessage:123`）。要填实例 id 而不是适配器类型名：AstrBot 的 `send_message` 按实例 id 匹配平台，写 `aiocqhttp:GroupMessage:123` 这种发不出去。

群名从哪来：群里来消息时顺手记（平台事件自带群名就直接用），首次见到某个群会后台问一次 `get_group_info`，点「刷新群列表」则调 `get_group_list` 一次补齐所有群 —— 所以**群里没说过话的群也能按群名选到**。名字缓存落在 `groups.json`，查不到名字就显示「群 群号」，不影响推送。

## 数据存储

- 推送去重记录：`data/plugin_data/astrbot_plugin_blue_protocol/push_record.json`
- 摘要缓存（24h）：同目录 `summary_cache.json`
- 公告长图缓存：同目录 `news_shots/`（按公告 id 哈希命名，保留最近 20 张 + 7 天兜底）
- 群名缓存（面板显示用）：同目录 `groups.json`（可删，删了只是面板里重新显示群号）

## License

MIT
