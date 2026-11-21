// 公告长图：顶部官方 KV 横幅 + 正文版心。
//
// 版式尺寸全部由宿主侧算好写进 data.json 的 style（单位 px，模板用
// style.scale 换算成 pt），这样配置里填的就是「像素」，和浏览器一致：
//   width  画布宽度（默认 1280px，等同常见浏览器宽度）
//   body   正文栏宽度（默认 1258px）
//   border 正文栏左右两侧留白（默认 11px）
// 主题（dark / light）、段间距、行高、模块间距同样由 style 传入。
//
// 正文按「块」排：kind = h1/h2/h3/h4（模块标题）、p（正文段落）、img（插图）。
// 模块标题上方留 module 间距，标题与正文之间再留一点，模块就不会挤成一坨。
#import "common.typ": *
#let d = json("data.json")
#let s = d.style
#let c = palette(d)
#let px(v) = v * s.scale * 1pt

#set page(width: px(s.width), height: auto, margin: 0pt, fill: c.bg)
#set text(font: font_of(d), size: px(s.font_body), fill: c.body)
// 段间距由每块的 gap 统一控制，所以这里的 par spacing 归零，
// 免得「块之间的留白」和「段之间的留白」叠加两次。
#set par(leading: px(s.font_body) * s.leading, spacing: 0pt)

#block(width: px(s.width))[
  #kv_banner(px(s.width), px(s.banner), url: d.at("kv", default: ""), c)
  #v(px(s.pad_top))

  #block(width: 100%, inset: (x: px(s.border)))[
    #block(width: 100%)[
      #block(inset: (x: 8pt, y: 3pt), fill: c.chip, radius: 3pt)[
        #text(size: px(s.font_tag), weight: "bold", fill: c.gold)[#d.tag]
      ]
      #v(10pt)
      #text(size: px(s.font_title), weight: "bold", fill: c.text)[#d.title]
      #v(8pt)
      #text(size: px(s.font_meta), fill: c.muted)[发布时间：#d.time]
    ]

    #if d.cover != "" {
      [
        #v(18pt)
        // 封面按正文栏宽度等比缩放，高度不裁剪（原图比例）
        #block(width: 100%)[
          #image(d.cover, width: 100%)
        ]
      ]
    }

    #v(20pt)
    #line(length: 100%, stroke: 0.6pt + c.line)
    #v(16pt)

    #for i in range(d.body.len()) {
      [#block_of(d.body.at(i), c, s)]
    }

    #v(14pt)
    #block(width: 100%, inset: 10pt, radius: 4pt, fill: c.panel)[
      #text(size: px(s.font_link), fill: c.link)[原文链接：#d.url]
    ]
    #v(14pt)
    #align(right, text(size: px(s.font_foot), fill: c.dim)[
      gm.qq.com · Blue Protocol: Star Resonance — 官方公告
    ])
  ]
]
