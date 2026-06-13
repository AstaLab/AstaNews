# 设计：把分类 / 初筛 / 解析从贵 agent 下放到脚本 + 小模型

> 状态：**提案（Approach A），待用户签字**。签字前不写任何实现代码。
> 背景对话：用户指出现在 layer 分类、重要度打分、解析都压在跑在 Claude Code 上的高成本 agent 上，规模化不了（成本高、并发差）。固定流程、不需要多方比对的环节应下放给脚本 + 便宜小模型 API。

## 1. 问题

当前 `daily-digest` pipeline 的第 3–6 步全由 agent 承担：

| 步 | 现在 | 性质 | 本设计 |
|---|---|---|---|
| 1 抓取 | 脚本 ✓ | 固定 | 不变 |
| 2 解析/抽正文 | 半脚本（RSS 直取，HTML 弱） | 固定 | **加 extract.py** |
| 3 去重+聚类 | 脚本 ✓ | 固定 | 暴露 cluster_size |
| **4 分类（layer 标签）** | **agent 逐条** | 固定 | **→ classify.py** |
| **5 粗筛+逐条 4 维打分** | **3–5 个 agent subagent** | 大半固定 | **→ prerank.py** |
| **6 重要度初筛/rank** | **agent editor** | 固定 | **→ prerank.py** |
| 7 终选（跨条目全局权衡、覆盖度、分 tier） | agent | **动态/多方比对** | 保留 agent，但只看 top~15 |
| 8 新闻体改写/锐评/深读 | agent | 半创造性 | 保留 agent |
| 9 嵌入/配图/发布 | 脚本 ✓ | 固定 | 不变 |

agent 现在要对 ~134 条候选逐条分类打分（3–5 个并行 subagent + editor）。本设计让脚本把 134 压到 ~15 再交给 agent，agent 只做不可替代的全局权衡与改写。

我们已有的免费资产让脚本化几乎零成本：
- **fastembed 本地 embedding 已部署**（语义检索用）→ 复用做零样本分类。
- **源注册表每个源带 `layers[]`** → 分类的免费先验。
- **dedup 已聚类** → "同一事件几个源报道了" = 多方比对的廉价版，直接当重要度信号。
- **extra 已抓到热度**（HN points / GitHub stars / HF likes）+ 源 priority（P0/P1/P2）。

## 2. 方案对比（待决）

- **A（推荐）确定性主力 + LLM 薄薄一层**：分类=embedding 零样本+源先验（零 LLM）；初筛=多信号确定性融合（零 LLM）→ top~30；LLM 只做两件薄事——低置信分类兜底、对 top~30 结构化重排到 ~15。没 key/没 ollama 时退化成纯确定性仍能跑。
- **B LLM 当初筛主力**：每条候选都让小模型结构化打分分类（把评分 subagent 1:1 换成便宜 LLM 调用）。简单直白，但每条都调 LLM、不透明、浪费已有免费信号。
- **C 全脚本零 LLM**：分类=embedding、初筛=确定性，一个 LLM 都不调。最省，但边界条目少了语义重要度判断。

本 spec 详述 A。B/C 仅作差异标注（§8）。

## 3. 供应商抽象：OpenAI 兼容接口

DeepSeek / 通义 / 智谱 / ollama 全是 OpenAI 兼容接口（`/v1/chat/completions`），ollama 本地在 `http://localhost:11434/v1` 暴露同一套。脚本只对**一个** OpenAI-style client 编程，`base_url + model + api_key` 进 config/env：

- 生产默认 → 国产便宜云 API。
- 开发自测 → 本机 ollama，不动生产 key。
- 换供应商 = 改一行配置。

`config/llm.yaml`（新）：
```yaml
enabled: true
base_url: https://api.deepseek.com/v1   # 生产默认；本地自测改 http://localhost:11434/v1
model: deepseek-chat                     # 本地自测改 qwen2.5:3b 等
api_key_env: ASTA_LLM_KEY                # key 进 .env，不进 git
temperature: 0
timeout: 30
```

## 4. 新增/改动脚本（黑盒，单一职责，自带 --help 与 --self-test）

### 4.1 `scripts/llm.py`（共享小模型 client）
- 薄封装 OpenAI 兼容 `chat.completions`。读 `config/llm.yaml`。
- 暴露 `chat_json(system, user) -> dict | None`：强制 JSON 输出、重试、**失败返回 None**（调用方据此退化）。
- 不被任何主流程硬依赖：`enabled:false` / 无 key / 连不上 → 返回 None，调用方走确定性。

### 4.2 `scripts/classify.py`（分类，零 LLM）
- 输入：候选 jsonl（含 title/summary/source）。
- 13 个 layer 各写一句中英混合「原型描述」（如 `serving: "推理服务、吞吐优化、vLLM/SGLang/TensorRT、KV cache、量化、inference serving throughput"`），嵌成 13 个锚向量（缓存到磁盘）。
- 候选嵌入（title+summary，复用 fastembed 同模型）→ 对 13 锚算余弦 → softmax。
- 与**源先验**融合：源 `layers[]` 命中的层加 boost（默认每层 ×1.3）。
- 输出每条加：`layer`（argmax）、`layers_ranked`（top-3 带分）、`layer_conf`（top1−top2 边际）、`cross_stack`（top-2 均过阈→true）。
- `layer_conf` 低于阈值 → `layer_uncertain:true`（供可选 LLM 兜底或 agent 关注）。
- 退化：无 fastembed → 用源首个声明层。
- 自测：~8 条带标注样例 → 断言 layer 正确率。

### 4.3 `scripts/prerank.py`（初筛打分 + 漏斗）
- 输入：classify 输出（含 cluster_size、extra 热度、源 priority、published）。
- 确定性分 = 归一化信号加权和（权重进 config）：
  - `source_priority`：P0=1.0 / P1=0.6 / P2=0.3
  - `recency`：窗口内按龄期指数衰减（越新越高）
  - `consensus`：cluster_size（多源）对数归一（1 源=0）
  - `leading_kw`：标题+摘要命中 SOTA/首次/首个/开源/release/outperforms/突破… 加分（封顶）
  - `heat`：extra 的 upvotes/points/stars/likes 分型对数归一
  - `cross_stack`：classify 给的跨层 → 小 boost
- 输出排序 jsonl，每条带 `prerank_score` + 各信号分项（透明可审）。`--keep N`（默认 30）切 top N。
- 可选 `--rerank --rerank-keep 15`：对 top-keep 调 `llm.chat_json` 要 `[{id, importance:0-10, reason}]`，与确定性分混合（`final=0.5*det_norm+0.5*imp/10`）重排，切到 rerank-keep。LLM 不可用 → 跳过重排，纯确定性结果。
- 自测：合成候选 → 断言「P0+SOTA+多源」排在「P2 bugfix 单源」之上。

### 4.4 `scripts/extract.py`（解析，零 LLM，可后置到 Phase 2）
- 对 html-type 源或摘要过薄的候选：fetch + trafilatura（规则法，无模型）抽正文 → 补 `clean_text` 与更好的 `summary`。
- 仅对需要的条目跑，单条失败跳过不阻塞。

## 5. SKILL.md pipeline 改动

第 3 步（并行评分 subagent fan-out）**删除**，替换为顺序跑脚本：
```bash
uv run classify.py --in fresh.jsonl --out classified.jsonl
uv run prerank.py  --in classified.jsonl --out ranked.jsonl --keep 30 [--rerank --rerank-keep 15]
```
第 4 步（editor 裁决）输入从「全部候选」变成 `ranked.jsonl` 的 top ~15（已分类、已打分、已排序）。agent 只做：终选 ~5（group）、分 tier、整理信息很全的记录。skill 明确写「分类与初筛已由脚本完成，你只做终选与改写；对 `layer_uncertain` 条目可复核」。第 5 步改写不变。

## 6. 健壮性 / 优雅退化

- 无 fastembed → classify 退化为源先验。
- 无 LLM（disabled / 无 key / 连不上）→ prerank 纯确定性、classify 不兜底。**pipeline 永不硬依赖 LLM**，云端 Actions 路径即使没 LLM key 也能跑。

## 7. 测试

- 每个脚本自带 `--self-test`（对齐现有 dedup/embed 的自测风格）。
- LLM 路径开发期指本机 ollama（如 `qwen2.5:3b`）验证，不动生产 key。
- 端到端：对一批合成候选跑 fetch→classify→prerank 干跑，核对分层与排序合理。

## 8. B/C 差异（备查）

- **B**：去掉 classify/prerank 的确定性核，改成对每条候选调 `llm.chat_json` 要 `{layer, importance, reason}`。`llm.py` 仍复用；prerank 退化为「按 LLM importance 排序」。代价：每条一次 LLM 调用。
- **C**：删掉 `--rerank` 与分类兜底，`llm.py` 不建。最简，纯确定性。

## 9. 不做（YAGNI）

- 不把改写（第 8 步）下放给小模型——本轮聚焦分类/初筛/解析，改写质量保留给 agent。
- 不引入向量数据库；分类锚向量用 numpy 缓存即可。
- 不做训练/微调分类器；零样本足够，不够再加 LLM 兜底。
