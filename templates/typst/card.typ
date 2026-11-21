// 公告卡片：官方 KV 铺满 + PPT 渐变遮罩 + 左上角分隔线，版心 400pt（≈800px @144PPI）。
//
// 与网页卡片（templates/card.html）同一套视觉：
//   ① kv.jpg 铺满（cover）；② 整体压暗底图后再叠 PPT 式斜向遮罩
//      （遮罩本身左上 0% 透明 → 右下 100% 不透明）；
//   ③ 左上角是官网 news-detail-bg.jpg 的蓝色分隔线；
//   ④ 文案放在半透明深色板上，压在高亮底图上也读得清。
#import "common.typ": *
#let d = json("data.json")
// 卡片是压在高亮 KV 上的分享图，固定深色配色。
#let c = palette(d)

#set page(width: 400pt, height: 360pt, margin: 0pt)
#set text(font: font_of(d), size: 9pt, fill: c.body)
#set par(leading: 0.62em, spacing: 5pt)

#block(width: 400pt, height: 360pt)[
  // ① 底图：官方 KV 铺满整张卡片（拿不到 KV 时退化为纯深色底）
  #if d.at("kv", default: "") != "" {
    [#place(top + left, image(d.kv, width: 400pt, height: 360pt, fit: "cover"))]
  }
  // ② 压暗底图（等价于网页版的 brightness），再叠 PPT 式斜向遮罩
  #place(top + left, rect(width: 400pt, height: 360pt, fill: rgb("05060A").transparentize(42%)))
  #place(top + left, rect(width: 400pt, height: 360pt, fill: scrim(angle: 45deg)))
  // ③ 官网分隔线（news-detail-bg.jpg 左上角的蓝色渐隐线）
  #place(top + left, rect(width: 110pt, height: 2.5pt, fill: gradient.linear(
    c.accent,
    c.accent.transparentize(100%),
    angle: 0deg,
  )))

  // ④ 文案板：半透明深色底，压在高亮底图上也读得清
  #block(width: 400pt, inset: (x: 20pt, y: 16pt))[
    #block(width: 100%, inset: (x: 14pt, y: 12pt), radius: 8pt, fill: rgb("06080E").transparentize(24%))[
      #text(size: 6.5pt, weight: "bold", fill: c.gold, tracking: 0.3pt)[
        BLUE PROTOCOL · STAR RESONANCE
      ]
      #v(4pt)
      #block(inset: (x: 7pt, y: 3pt), fill: c.gold.transparentize(84%), radius: 3pt)[
        #text(size: 8pt, weight: "bold", fill: c.gold)[#d.tag]
      ]
      #v(7pt)
      #text(size: 18pt, weight: "bold", fill: white)[#d.title]
      #v(6pt)
      #text(size: 8.5pt, fill: rgb("D9DDE6"))[发布时间：#d.time]

      #if d.desc != "" {
        [
          #v(10pt)
          #text(size: 9.5pt, fill: rgb("EDEFF4"))[#d.desc]
        ]
      }
    ]
  ]

  // 底部：分隔线 + 原文链接 + 署名
  #place(bottom + left, box(width: 400pt, inset: (x: 20pt, y: 16pt))[
    #line(length: 100%, stroke: 0.8pt + c.gold.transparentize(45%))
    #v(9pt)
    #block(width: 100%, inset: 8pt, radius: 5pt, fill: rgb("0A0D14").transparentize(40%))[
      #text(size: 8pt, fill: c.link)[原文链接：#d.url]
    ]
    #v(9pt)
    #align(right, text(size: 7pt, fill: rgb("A6ACBA"))[
      gm.qq.com · Blue Protocol: Star Resonance — 官方公告
    ])
  ])
]
