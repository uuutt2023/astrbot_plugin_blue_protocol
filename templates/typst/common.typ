// 共享样式：颜色、字体、KV 遮罩、正文行内片段。
//
// 排版方案参考 SXP-Simon/astrbot_plugin_qq_group_daily_analysis：
// 版心按 144 PPI 栅格化，长图 195pt ≈ 390px、卡片 400pt ≈ 800px。
// 正文一律来自 data.json 的字符串，模板不执行任何外部代码。
//
// 渐变角度（Typst 实测）：0°=左→右，90°=上→下，45°=左上→右下。

#let c = (
  bg: rgb("0F1218"),
  text: rgb("ECEDF2"),
  body: rgb("E4E6EC"),
  muted: rgb("A8ACB8"),
  dim: rgb("8A8E9C"),
  gold: rgb("FFD76E"),
  link: rgb("9CC0F5"),
  line: rgb("2A3040"),
  accent: rgb("4FC3F7"),
)

// 字体名由宿主侧解析后写进 data.json（data.font），
// 避免模板里列一堆系统上并不存在的字族而刷出一屏 warning。
#let font_of(d) = d.at("font", default: "Noto Sans CJK SC")

// PPT 式遮罩：左上 0% 透明 → 右下 100% 不透明。
#let scrim(angle: 45deg) = gradient.linear(
  rgb("080A10").transparentize(100%),
  rgb("05060A"),
  angle: angle,
)

// 竖向遮罩：横幅顶亮底暗，标题压在下面。
#let fade_down() = gradient.linear(
  rgb("0A0C14").transparentize(100%),
  rgb("0A0C14"),
  angle: 90deg,
)

// 公告正文行内片段。片段文本是 JSON 字符串，Typst 按纯文本渲染，无需转义。
#let runs(parts) = {
  for part in parts {
    if "br" in part {
      linebreak()
    } else {
      text(
        weight: if part.at("b", default: false) { "bold" } else { "regular" },
        style: if part.at("i", default: false) { "italic" } else { "normal" },
        fill: if part.at("s", default: false) { c.dim } else { c.body },
      )[#part.at("t", default: "")]
    }
  }
}

// 官方 KV 横幅（长图顶部）。width / height 是版心内的实际尺寸。
#let kv_banner(width, height, url: "kv.jpg") = box(width: width, height: height)[
  #if url != "" {
    [#place(top + left, image(url, width: width, height: height, fit: "cover"))]
  }
  #place(top + left, rect(width: width, height: height, fill: fade_down()))
  #place(bottom + left, box(width: width, inset: (x: 9pt, y: 7pt))[
    #text(size: 7pt, weight: "bold", fill: c.gold, tracking: 0.3pt,
      stroke: 0.5pt + rgb("0A0C14").transparentize(40%))[
      BLUE PROTOCOL · STAR RESONANCE
    ]
    #h(3pt)
    #text(size: 6pt, fill: rgb("E6E9F0"),
      stroke: 0.4pt + rgb("0A0C14").transparentize(45%))[官方公告]
  ])
]
