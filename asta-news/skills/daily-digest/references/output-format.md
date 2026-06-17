# Digest 输出模板

两个产物用同一份数据：**digest.json**（喂静态站点，信息全）和 **archive/<date>.md**（微信可读，给人看）。中文为主，专有名词/术语保留英文。

## digest.json schema v2（多级 + 多视角；站点与 publish_site.py 依赖）

v2 在 v1 基础上加 `tiers` 与 `perspectives`，并保留 `selected`/`all_candidates` 向后兼容：
```jsonc
{
  "date","weekday","headline","overview","stats","schema_version":2,
  "tiers": {
    "group": [ {rank,layer,source,title,summary,deep,readable(微信),facts,links,scores,image?} ], // ~group.target（见 config/tiers.yaml）
    "daily": [ {id,layer,source,title,summary,deep,facts,links,score,image?} ],                    // ~daily.target（见 config/tiers.yaml），含 group
    "full":  [ {source,layer,title,url,summary,selected} ]                                         // 全部候选，不限量
  },
  // 每条两层正文（见 references/readiness.md）：
  //   summary = 列表卡片用的摘要 = 一段完整的话（约 150-260 字 / 3-5 句，单段不换行）
  //   deep    = 详情页 /item/ 正文 = 深度全文解读，比摘要更深更详细（~600-1000 字 / 5-8 段）
  //   readable= 仅 group 需要：微信群发的新闻体 3-4 段（concise）。daily 非精选无需 readable。
  //   ⚠️ 列表是摘要、点进去要更详细——summary 与 deep 不能是同一段，deep 必须真正展开。
  // overview（日报摘要）汇总多条新闻：必须用 \n 换行把不同新闻簇分开（前端 white-space:pre-line 渲染）；单条 summary 不分行。
  "perspectives": { "technical":{"lede":"…"},"product":{…},"business":{…},"research":{…},"embodied":{…} },
  "radar":[…], "gaps":[…],
  "selected": "= tiers.group（兼容）", "all_candidates": "= tiers.full（兼容）"
}
```
item 可选 `image`: `{url, credit, source}`（配图，见 enrich-images skill / scripts/enrich_images.py）。

## v1 字段（兼容保留）

```json
{
  "date": "2026-06-12",
  "weekday": "周五",
  "headline": "一行短标题，≤24 字、两个对称分句（如『前沿实验室扎堆冲 IPO，技术面多点开花』）；不堆三段以上、不是流程说明。站点主标题是日期，headline 只作归档列表副标题与 SEO",
  "overview": "当期摘要(abstract)：新闻体 1–2 段、约 200–360 字，自成一体讲清当天主线与几条重点；站点作为日期标题下的正文摘要单独成段。只讲新闻，禁止条数/窗口/'剔除旧论文'等策展过程话术",
  "stats": {"candidates": 483, "sources_ok": 25, "sources_failed": 2,
            "layers_covered": ["model", "embodied", "safety", "devtool", "agent"]},
  "selected": [
    {"rank": 1, "layer": "model", "source": "hf-trending-models",
     "title": "忠实转述的中文标题",
     "readable": "Readiness 改写的微信版正文，3-5 句，可含换行",
     "facts": ["1T 总参/32B 激活", "KCB v2 自报 62.0", "..."],
     "links": {"primary": "一手源 url", "discussion": "HN/HF 讨论 url（可选）"},
     "scores": {"novelty": 4, "leading_edge": 3, "impact": 4, "cross_stack": 3}}
  ],
  "radar": [{"layer": "model", "title": "一句话", "note": "为什么留雷达", "link": "url"}],
  "gaps": ["RSSHub 未部署：…", "X List 未配置：…"],
  "all_candidates": [{"source": "arxiv-cs-lg", "layer": "post-training",
                      "title": "...", "url": "...", "summary": "原摘要截断~240字", "selected": false}]
}
```

`all_candidates` 是 fresh.jsonl 全部条目降维（layer 取第一个，summary 取原摘要截断 ~240 字）——网页"全部信息"区据此展示当天所有候选（标题 + 原文链接 + 摘要），精选标星。这是"完整展示全部信息"的落点。

## archive/<date>.md（微信可读版）

每条回答"为什么值得花 30 秒"，给量化事实不给形容词。正文用各条的 `readable`。

## Markdown 模板（archive 与会话输出共用）

```markdown
# 🛰️ AstaNews — {YYYY-MM-DD}（{星期}）

> {一句话当日总览：今天的主线是什么。没有主线就写最大的一条。}

## 1. {layer_emoji} [{layer}] {标题（中文转述，关键专名保留英文）}

{2-4 句：这是什么 / 为什么重要 / 量化点。}

🔗 [一手源]({primary_url}){ · [HN 讨论 N 评]({hn_url}) 等附注链接}

## 2. …（共 {N} 条，N ≤ 8）

---

### 📡 雷达

{落选但接近的 3-5 条，每条一行：[layer] 标题 — 一句话 + 链接}

### ⚠️ 数据缺口

{抓取失败/跳过的源及原因，一行一个；全部正常则写"全部源正常"。}

*{N} 条 · 覆盖 {layers 列表} · 候选 {M} 条 · AstaNews*
```

## Layer emoji 对照

model 🧠 · post-training 🎛️ · eval 📊 · data 🗂️ · infra 🏗️ · serving ⚡ · maas ☁️ ·
agent 🤖 · embodied 🦾 · safety 🛡️ · product 📦 · business 💰 · devtool 🔧

## 条目写法

- 标题忠于事实，不标题党：`vLLM v0.23 落地 FP4 推理，H100 吞吐 +38%`，而不是 `vLLM 重大更新！`。
- 第一句说清"是什么"；第二句"为什么重要"（对哪类从业者意味着什么）；量化点编织进句子。
- 论文条目：给出关键数字（基准分/参数量/数据规模），注明是否有代码/权重。
- 发布条目：明确版本号与可用性（开源？API？哪些 region？价格？）。

## 投递格式注意

- 默认交付 = 会话全文输出 + archive 落盘。外部接管投递（如 Telegram）时：
  - Telegram 用 parse_mode=HTML；`<pre>` 内的缩进必须用 U+00A0（普通空格会被客户端吞掉）。
  - 超长拆多条，标题加 `(1/N)` 后缀。
