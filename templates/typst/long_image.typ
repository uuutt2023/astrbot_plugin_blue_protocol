// 公告长图：顶部官方 KV 横幅 + 深色正文，版心 195pt（≈390px @144PPI）。
#import "common.typ": *
#let d = json("data.json")

#set page(width: 195pt, height: auto, margin: 0pt, fill: c.bg)
#set text(font: font_of(d), size: 9pt, fill: c.body)
#set par(leading: 0.62em, spacing: 5pt)

#block(width: 195pt)[
  #kv_banner(195pt, 62pt, url: d.at("kv", default: ""))
  #v(9pt)
  #block(width: 100%, inset: (x: 9pt))[
    #block(inset: (x: 5pt, y: 2pt), fill: c.gold.transparentize(85%), radius: 2.5pt)[
      #text(size: 6.5pt, weight: "bold", fill: c.gold)[#d.tag]
    ]
    #v(4pt)
    #text(size: 12.5pt, weight: "bold", fill: white)[#d.title]
    #v(3pt)
    #text(size: 7pt, fill: c.muted)[发布时间：#d.time]

    #if d.cover != "" {
      [
        #v(7pt)
        #block(width: 100%, radius: 4pt, clip: true)[
          #image(d.cover, width: 100%, fit: "cover")
        ]
      ]
    }

    #v(9pt)
    #line(length: 100%, stroke: 0.6pt + c.line)
    #v(7pt)

    #for p in d.body {
      [#runs(p.runs) #parbreak()]
    }

    #v(3pt)
    #block(width: 100%, inset: 6pt, radius: 3pt, fill: rgb("11151F"))[
      #text(size: 6.5pt, fill: c.link)[原文链接：#d.url]
    ]
    #v(8pt)
    #align(right, text(size: 6pt, fill: c.dim)[
      gm.qq.com · Blue Protocol: Star Resonance — 官方公告
    ])
  ]
]
