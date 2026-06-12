# 如何配图（用图说话，借鉴橘鸦）

日报与网页都要配图。两条路线，按 tier 用：

## A. 精选（group）——AI 主动找"信息图"（首选）

精选是头条，值得 agent 花力气找**最能说明问题的那张图**，而不是随便一张 og:image。按条目类型找：

- **模型发布**：找它的**评测/基准对比图**（benchmark chart、雷达图、Elo 对比）——一张图看清它强在哪、和谁比。次选架构图。
- **论文**：找**关键图**——架构图（teaser/Figure 1）、主结果曲线/表。arXiv 没有 og:image，但 `https://ar5iv.org/abs/<id>` 或 `https://arxiv.org/html/<id>` 的 HTML 版里有 `<img>`，第一张通常是架构/teaser；取其绝对 URL。
- **产品/工具**：找**界面截图 / 演示图 / 流程图**。
- **融资/商业**：一般无信息图，可不配或用公司 logo。

做法：agent 用 WebFetch 打开一手页面（或其 HTML 版、博客、HF 卡片），挑出最有信息量的 `<img>` 的绝对 URL；**必须验证该 URL 真的是图片**（HEAD/GET 看 content-type 是 image/*，或扩展名 .png/.jpg/.webp，且能在浏览器打开）。被墙域名走 `ASTA_PROXY`。
记 `image = {url, credit:来源域名, source:页面 URL, why:为什么选这张（如"官方公布的 KCB v2 对比图"）}`。
找不到合适的信息图就退到 B，再不行就不配（前端用 layer 主题色兜底，不放无关图）。

## B. 全员（group+daily）——脚本抓 og:image（兜底/批量）

`scripts/enrich_images.py` 自动抓 og:image / twitter:image / GitHub 社交预览 / HF 社交缩略图。批量、便宜、覆盖 ~一半。
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/enrich_images.py --edition <digest.json> --tiers group,daily
```
脚本只在条目还没 `image` 时填——所以**先做 A（精选信息图），再跑 B 补 daily 与漏网的**。

## 版权与失败兜底
- `credit` 记来源域名，前端可标注。优先官方一手源的图。
- 不确定/抓不到 → 宁可不配，也不要放无关或误导的图（前端 layer 色块兜底已够体面）。
- 图要能直链（防盗链的换源或不用）。
