# -*- coding: utf-8 -*-
"""Blue Protocol: Star Resonance 公告插件的子包。

- ``api``        腾讯游戏官网 wmp/v3.1 接口（列表 / 详情）
- ``layout``     长图版式（几何 / 主题 / 段间距 / 行高），Typst 与 HTML 共用
- ``render``     正文 → 长图 HTML / 兜底卡片数据
- ``screenshot`` Playwright 视口长图
- ``typst``      本地 Typst 排版（长图 / 卡片）
- ``groups``     群名解析（面板按群名选群）
- ``page``       Web 面板后端接口
"""

__all__ = ["api", "layout", "render", "screenshot", "typst", "groups", "page"]
