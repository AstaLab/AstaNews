# Digest 输出模板

两个产物用同一份数据：**digest.json**（喂静态站点，信息全）和 **archive/<date>.md**（微信可读，给人看）。中文为主，专有名词/术语保留英文。

## digest.json schema（站点与 publish_site.py 依赖）

```json
{
  "date": "2026-06-12",
  "weekday": "星期五",
  "headline": "标题（≤20 字，抓主线）",
  "overview": "一句话当日总览：今天的主线是什么",
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
                      "title": "...", "url": "...", "selected": false}]
}
```

`all_candidates` 是 fresh.jsonl 全部条目降维（layer 取第一个即可）——网页"全部信息"区据此展示当天所有候选，精选标星。这是"完整展示全部信息"的落点。

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
