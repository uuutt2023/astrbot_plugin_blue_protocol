// 共享样式：调色板、字体、KV 遮罩、正文行内片段。
//
// 排版方案参考 SXP-Simon/astrbot_plugin_qq_group_daily_analysis：
// 版式参数由宿主侧算好（px → pt）写进 data.json，模板只负责排版，
// 正文一律来自 data.json 的字符串，模板不执行任何外部代码。
//
// 渐变角度（Typst 实测）：0°=左→右，90°=上→下，45°=左上→右下。

// 配色由宿主侧写进 data.json（data.colors），Typst 与 HTML 两条路共用同一份，
// 主题切换不会出现「一边深色一边浅色」。
#let palette(d) = {
  let c = d.at("colors", default: (:))
  (
    bg: rgb(c.at("bg", default: "0F1218")),
    text: rgb(c.at("text", default: "ECEDF2")),
    body: rgb(c.at("body", default: "E4E6EC")),
    muted: rgb(c.at("muted", default: "A8ACB8")),
    dim: rgb(c.at("dim", default: "8A8E9C")),
    gold: rgb(c.at("gold", default: "FFD76E")),
    link: rgb(c.at("link", default: "9CC0F5")),
    line: rgb(c.at("line", default: "2A3040")),
    chip: rgb(c.at("chip", default: "2C281B")),
    panel: rgb(c.at("panel", default: "11151F")),
    kv_text: rgb(c.at("kv_text", default: "E6E9F0")),
    accent: rgb(c.at("accent", default: "4FC3F7")),
  )
}

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
#let runs(parts, c) = {
  for part in parts {
    if "br" in part {
      linebreak()
    } else {
      let body = text(
        weight: if part.at("b", default: false) { "bold" } else { "regular" },
        style: if part.at("i", default: false) { "italic" } else { "normal" },
        fill: if part.at("s", default: false) { c.dim } else { c.body },
      )[#part.at("t", default: "")]
      let href = part.at("href", default: "")
      if href != "" { link(href)[#body] } else { body }
    }
  }
}

// 模块标题。h1/h2 是大模块（带金色竖条），h3/h4 是小模块。
//
// 上方留 module 间距（模块之间的呼吸感），下方留一点，和正文拉开距离。
#let heading(blk, c, s, level: 2) = {
  let px(v) = v * s.scale * 1pt
  let big = level <= 2
  let size = if big { px(s.font_h2) } else { px(s.font_h3) }
  [
    #block(width: 100%)[
      #set par(leading: size * 1.35)
      #if big {
        [
          // 金色竖条：模块和正文之间最直接的视觉分界
          #place(left + horizon, rect(
            width: px(3),
            height: 1em,
            fill: c.gold,
          ))
          #h(px(9))
        ]
      }
      #text(size: size, weight: "bold", fill: c.text)[
        #runs(blk.at("runs", default: ()), c)
      ]
    ]
  ]
}

// 正文段落。
#let paragraph(blk, c) = {
  block(width: 100%)[#runs(blk.at("runs", default: ()), c)]
}

// 公告内嵌插图：按版心宽度等比缩放（小图不放大，和网页的 max-width 一致）。
#let picture(blk, c, s) = {
  let px(v) = v * s.scale * 1pt
  let src = blk.at("src", default: "")
  if src != "" {
    let w = blk.at("w", default: 0)
    [
      #block(width: 100%)[
        #if w > 0 { image(src, width: px(w)) } else { image(src, width: 100%) }
      ]
    ]
  }
}

// 一个排版块。块上方的留白由宿主侧算好（gap），两条渲染路径共用同一份。
#let block_of(blk, c, s) = {
  let px(v) = v * s.scale * 1pt
  let kind = blk.at("kind", default: "p")
  // 注意：if/else 链必须留在代码模式里，放进 [...] 内容块会被当成正文排出来
  let body = if kind == "h1" {
    heading(blk, c, s, level: 1)
  } else if kind == "h2" {
    heading(blk, c, s, level: 2)
  } else if kind == "h3" {
    heading(blk, c, s, level: 3)
  } else if kind == "h4" {
    heading(blk, c, s, level: 4)
  } else if kind == "img" {
    picture(blk, c, s)
  } else {
    paragraph(blk, c)
  }
  [#v(px(blk.at("gap", default: 0))) #body]
}

// 官方 KV 横幅（长图顶部）。width / height 是版心内的实际尺寸。
#let kv_banner(width, height, url: "kv.jpg", c) = box(width: width, height: height)[
  #if url != "" {
    [#place(top + left, image(url, width: width, height: height, fit: "cover"))]
  }
  #place(top + left, rect(width: width, height: height, fill: fade_down()))
  #place(bottom + left, box(width: width, inset: (x: 18pt, y: 14pt))[
    #text(size: 7.5pt, weight: "bold", fill: c.gold, tracking: 0.3pt,
      stroke: 0.5pt + rgb("0A0C14").transparentize(40%))[
      BLUE PROTOCOL · STAR RESONANCE
    ]
    #h(4pt)
    #text(size: 6.5pt, fill: c.kv_text,
      stroke: 0.4pt + rgb("0A0C14").transparentize(45%))[官方公告]
  ])
]
