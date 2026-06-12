# 橘鸦 AI 早报研究 + 公众号发布路径

来源：[md2juya（复刻橘鸦样式）](https://github.com/MurphyLo/md2juya)、[md2wechat-skill](https://github.com/geekjourneyx/md2wechat-skill)、[知乎·我的 AI 实践：橘鸦 AI 早报](https://zhuanlan.zhihu.com/p/1981801799909406717)、[少数派·搞定公众号配图](https://sspai.com/post/92138)。

## 橘鸦的排版/写法（要点）

- **单条**：编号 `## 标题 #N`（米色底/绿底线/圆角）→ **导语**（引用块，米色圆角，一句话抓核心）→ 正文（段落+列表+表格+内联代码强调术语）→ **配图**（圆角居中，自适应）。
- **整期**：顶部全宽标题图 → 橘色大标题 → **概览**（自动编号的无序列表，先把当天几条列出来）→ 虚线分割 → 各条循环。
- **视觉**：米色+橘色主色、虚线分割线、表格奇偶行交替、卡片化、emoji。
- **生成**：marked.js 自定义渲染器把 markdown 转成 HTML 片段（无 html/body），≤1MB 满足微信 API。

## 对 AstaNews 的启示

1. **我们的 gazette 美学已经天然接近橘鸦**：暖纸米色 + 朱砂(≈橘) + 圆角卡片 + 虚线分割 + emoji 层标签 + mono 强调术语。无需大改。
2. **借鉴：今日概览数字列表** —— 橘鸦每期开头先用编号列表把当天几条列出来，扫读性好。已应用到我们的微信版 `editions/<date>.md`（overview 后加"今日概览"精选列表）。✅
3. **导语高亮** —— 单条第一句作"关你什么事"的钩子（我们 readiness 已这么写，呈现上可考虑加重）。
4. **用图说话** —— 我们已做（og:image + AI 找信息图）；橘鸦的图多为示意/产品/数据图，与我们方向一致。

## 公众号自动发布路径（P3-WECHAT 的具体落法）

我们已有干净的每日 markdown（`editions/<date>.md`，精选新闻体 + 链接）。发布到公众号的成熟路径：

```
editions/<date>.md  →  md2juya / md2wechat-skill（markdown → 橘鸦风 HTML 片段，可 AI 配图）
                    →  微信公众号「草稿/发布」API（draft.add → freepublish.submit）
```

- **排版**：直接复用 md2juya（橘鸦风）或 md2wechat（40+ 主题）把我们的 md 转成公众号 HTML 片段。
- **配图**：微信后台自带 AI 配图，或我们已抓的 image 字段直接嵌入。
- **发布**：微信公众号开放 API（需公众号 appid/secret + 服务器 IP 白名单）。这步要用户的公众号凭证，留给有号之后接入。
- **接入点**：在 `asta-news/scripts/` 加 `publish_wechat.py`（读 editions md + image → 调 md2wechat 转 HTML → 调公众号 API），由 services 后端 `/api/publish/wechat` 触发，网站控制台一个按钮。凭证走 require_auth + 环境变量。

## 结论
橘鸦的"易懂 + 配图 + 商业视角"我们已基本对齐（新闻体改写、配图、中文商业源、商业视角 filter）。剩下的增量主要是**公众号这条发布管道**（凭证就绪后按上面路径接 md2wechat + 微信 API）。
