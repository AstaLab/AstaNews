# AstaNews 原理

> 这份文档解释系统为什么长这样。改 pipeline、加源、调规则之前请先读完——大部分"看起来可以简化"的地方背后都有一条真实踩过的坑。

## 设计目标

每天从 AI 全栈 13 层（model / post-training / eval / data / infra / serving / maas / agent / embodied / safety / product / business / devtool）的一手信息源里，策展出**默认 5 条、最多 8 条、覆盖 ≥3 层**的 digest。三条铁律：宁缺毋滥、全栈视野、新与领先优先。

核心矛盾：每天有 400+ 条候选，但读者只该看 5 条。所以系统的本质不是"聚合器"，而是一条**漏斗**：

```
~98 个源 ──fetch──▶ ~450 候选 ──dedup──▶ ~430 新条目 ──subagent 评分──▶ ~20 推荐 ──editor──▶ 5-8 条
```

## 一、三层架构：什么交给脚本，什么交给 agent

| 层 | 承担什么 | 为什么 |
|---|---|---|
| **确定性脚本层**（`scripts/`） | 抓取、解析、去重、健康检查 | 这些工作要的是稳定和便宜，LLM 在这里只会引入不确定性。脚本是黑盒（PEP 723 + `uv run` 零安装），agent 只看 `--help` 不读源码，避免污染上下文 |
| **Agent 策展层**（`skills/daily-digest/`） | 粗筛、评分、核实、裁决、撰写 | 这些工作要的是判断力。SKILL.md 是工作流，评分细则在 `references/curation.md`（按需加载，渐进披露） |
| **数据层** | `sources/*.yaml`（社区默认表）+ `~/.claude/plugins/data/asta-news/`（本地状态） | 代码与数据分离：贡献源不用碰代码；plugin 升级不会清掉用户状态 |

## 一·补：两道成稿关 — 先"信息全"，再"看得懂"

"提取信息"和"写得好看"是两种能力，混在一起两边都打折。所以裁决之后分两关：

1. **信息很全的结构化记录**（editor 产出）：每个入选条目带尽量全的 `facts`、`why_matters`、`links`、`scores`。这一步只管不丢事实、不搞错。
2. **Readiness 改写**（独立 subagent，见 `references/readiness.md`）：拿着上一步的完整记录，改写成微信群跨栈受众（都是 AI 人但分布在不同技术栈）读得下去的稿子——先一句话桥接"关你什么事"，保留一个技术锚点并解释，诚实标注保留（自报基准/未发 notes），3-5 句，不丢任何数字。把完整 facts 喂给改写 agent 而不是让它自己记，正是为了改写时不写错。

## 一·补二：两个产物，一个网页

每天的 digest 同时产出两样东西，喂给不同消费者：

- **`archive/<date>.md`**：微信可读版，直接粘进群。
- **`digest.json`**：结构化全量产物——精选（带 readable + facts）+ 雷达 + 数据缺口 + **全部候选 all_candidates**（当天抓到的每一条，不只精选）。`publish_site.py` 把它发布到 `site/data/<date>.json` 并重建 `index.json`。

`site/` 是纯客户端静态站（vanilla JS，无构建），从 `data/` 自动加载渲染：精选卡片、雷达、数据缺口、以及一个可展开的"全部信息"区——把当天全部候选按源分组列出、精选标星。**这是"完整展示全部信息"的落点**：精选是为微信做的减法，要全景就看网页。

发布即更新。本地预览 `cd site && python3 -m http.server 8000`。

## 一·补三：部署模型 — 仓库就是部署单元

不要把产物当本地状态——它们进 git，由 GitHub 跑、GitHub 渲染。闭环（`.github/workflows/daily-digest.yml`）：

```
cron(每天 UTC 01:00) → checkout 仓库（带历史 editions）→ uv + claude-code
  → claude -p "/asta-news:daily-digest"（产物写进仓库 site/data + editions）
  → git commit & push → upload-pages-artifact(./site) → deploy-pages → 网页自动更新
```

几个关键点：

- **GitHub runner 在墙外**：`needs_proxy` 的源（HF/Google/Reddit/Mistral…）在 runner 上**直连**即可，不设 `ASTA_PROXY`——所以 Actions 模式的数据覆盖反而比本机更全。只有 RSSHub 类源（X/量子位）在 runner 上没有实例会进数据缺口（Anthropic 等可由策展 agent 直接 WebFetch 官网兜底）。
- **仓库即去重状态**：`dedup.py --seen-from site/data` 从历史 digest.json 重建已见 URL 集合，不依赖任何本地 db。每天 commit 的 `digest.json` 就是第二天的状态源——无状态、可重放、可 diff。
- **产物落点**：`ASTA_OUTPUT_DIR` 指向仓库 `site/`，`publish_site.py` 一步写 `site/data/<date>.json`（网页数据，唯一事实源）+ `site/data/index.json`（归档索引）+ `editions/<date>.md`（微信版，json 生成不漂移）。中间产物（candidates/fresh）留在 `ASTA_NEWS_HOME` 临时目录，不进 git。
- **唯一密钥**：仓库 secret `ANTHROPIC_API_KEY`。其余（`GITHUB_ACCESS_TOKEN`）用 Actions 自带的 `github.token`。

本地交互模式（用户在装好的 plugin 里手跑）仍可用——产物落本地 data dir、去重用 seen.db。两种模式同一套脚本，靠 `$OUT/data` 是否存在历史来区分。

## 二、数据流逐步拆解

### 1. 抓取（fetch_sources.py）

- **注册表合并**：`sources/*.yaml`（仓库默认，PR 贡献）+ `sources.local.yaml`（个人，同 id 覆盖）。
- **并发 + best-effort**：8 线程，单源失败只记警告绝不拖垮整体——情报系统的首要可用性原则是"缺一个源也要出报"。
- **六种 type**：`rss`/`atom`/`github-releases` 走 feedparser；`json` 按 `parser` 字段分发到 14 个防御式解析器；`rsshub` 经自部署实例；`html` **不抓**——只登记 URL 给策展 agent 按需阅读（CSS 选择器爬 JS 站必然腐烂，这是评估 5 个同类项目得出的统一教训）。
- **diff 型源**：榜单（SWE-bench/EvalPlus/Aider）和目录（OpenRouter models）没有"发布时间"概念，靠与本地快照（`runs/state/*.json`）对比报增量。三条保护：首跑只建快照不报（防全量刷屏）、空 payload 拒绝覆盖快照（防故障恢复后误报全量）、原子写入（防损坏永久卡死）。
- **时间窗**：默认 36h（`rules.scoring.window_hours`），覆盖时差与隔夜积压；arXiv 周末不更新，零候选属正常。

### 2. 去重（dedup.py，SQLite `seen.db`，14 天滑窗）

两层判重，每层都有一个被实测打过脸的细节：

- **URL 规范化精确匹配**：去 tracking 参数用**黑名单制**（utm_*/fbclid/...）而不是白名单制——白名单会把微信公众号链接（身份全在 query 参数里）全部误判成同一篇。另：arXiv 的 pdf/abs/版本号统一归一。
- **模糊标题匹配**（difflib ≥0.78）：先比**数字/版本 token**——"vLLM v0.23.0" 与 "v0.22.0" 相似度 0.96，但它们是两次发布，token 不同直接判不同事件。
- **失败开放**：库损坏放行全部、单条数据异常只放行该条。宁可重复，不可漏报。

### 3. 并行富化评分（subagent fan-out）

候选按层分 3-5 组并行派 subagent，每个 agent：粗筛 → 对幸存者**逐条**打四维分（批量打分会致幻——ArxivDigest 的代码里自带 hallucination warning）→ 写事实依据。关键纪律：

- **四维加权**：novelty 0.35 + leading_edge 0.30 + impact 0.25 + cross_stack 0.10，锚点定义在 curation.md。novelty 看信息增量不看发布日期。
- **事实接地**：每条必须有一个量化点，**只许用原文已述内容**，原文没有就写"原文未给出量化数据"（继承 daily-ai-papers 的 prompt 纪律）。
- **失败即弃选**：评分失败/拿不准 = recommend false。参考项目 customize-arxiv-daily 的反面教材：LLM 失败给满分，垃圾全部置顶。
- **防致幻校验**：返回的 id 必须在输入集合内，多出的丢弃。

### 3·补：分类 / 初筛 / 解析脚本化（P1-SCRIPTIFY — 增量件已建并自测，SKILL 接线待签字）

把固定、非动态、不需多方比对的活从贵 agent 下放到脚本 + 便宜小模型，是成本规模化的关键：agent 逐条扫上百候选既慢又贵，而"打 layer 标签 / 按重要度初筛 / 抽正文"本质都是确定性流程。增量脚本（纯新增、自测全绿、现有 pipeline 未改）：

- **`classify.py`**：embedding 零样本分类。13 层各一句中英原型描述嵌成锚向量（复用 fastembed 同模型），候选对锚算余弦 + 融合候选自带的源声明 `layers[]` 先验 → 定单层 + 置信度 + 跨层标记。零 LLM。
- **`prerank.py` + `config/prerank.yaml`**：多信号确定性打分。源权威(P0/P1/P2) + 新鲜度(指数衰减) + 多源共识(dedup 聚类大小，多方比对的廉价版) + 领先/首次关键词 + 热度 → 排序、压到 ~30；可选小模型对 top-N 结构化重排到 ~15。
- **`extract.py`**：trafilatura 规则法抽正文，给摘要过薄的候选回填，零 LLM、失败开放。
- **`llm.py` + `config/llm.yaml`**：OpenAI 兼容小模型 client（DeepSeek/通义/智谱/ollama 同一接口，base_url+model+key 进 config，生产默认便宜云、自测走本地 ollama）。不可用即优雅退化为纯确定性——pipeline 永不硬依赖 LLM。

接线后，上面 二.3 的 subagent fan-out 由 `extract→classify→prerank` 取代，agent 只对排好的 top ~15 终选 + 改写。这是唯一改生产行为的一步，gate 在用户拍 A/B/C（设计见 `docs/superpowers/specs/2026-06-13-scriptify-classify-rank-design.md`）。**接线前，二.3 描述的仍是当前生产路径。**

### 4. Editor 裁决

负向兴趣（`profile.md`）一票否决 → 同事件合并（一手源优先，HN/HF 讨论降为附注）→ 加权排序 → 约束校验（≥3 层、单层 ≤2、单源 ≤2）→ 落选但接近的进"雷达"。**抓取失败的源必须写进"数据缺口"**——读者要能区分"没发生"和"没看到"。

### 5. 归档与登记

digest 写 `archive/YYYY-MM-DD.md`（这同时就是已推送台账），入选条目登记 `published`、雷达条目登记 `considered` 进 seen.db——第二天它们不会再成为候选（幂等性是实测验收项）。

## 三、网络层（GFW 环境的工程现实）

- **直连优先，代理兜底**：脚本只认 `ASTA_PROXY`（显式管理），并把 `requests` 的 `trust_env` 关掉——IDE/会话注入的 `HTTPS_PROXY` 是内部代理，会劫持并搞挂 github.com 直连请求（实测）。
- `needs_proxy: true` 的源（HF/Google/Mistral/Anthropic/Reddit-RSS 等）强制走代理；没配代理就跳过并如实进数据缺口。
- **RSSHub 是"无 feed 源的统一适配层"**：X/Twitter、Anthropic、量子位、GitHub Trending 都没有可用原生 feed，自部署一个 RSSHub（docker compose，`restart: always`，一次 init 永久自治）把它们全部变成标准 RSS。凭证（x.com 的 auth_token cookie、GitHub PAT）只进容器 `.env`，不进 shell 环境也不进任何会提交的文件。
- 已知无解的墙：Meta AI blog 对直连和代理一律 bot 墙 400——自动管线放弃，由 HN/transformers releases 兜底，急需时策展 agent 用 agent-browser 渲染。

## 四、源注册表的质量机制

- **P0/P1/P2**：P0 每日必抓且影响裁决；P1 增强；P2 按需/备用。日常抓 P0+P1。
- **加源必须先 probe**：`probe_source.py` 验证可达 + 可解析 + **新鲜度**（最新条目时间 vs freq 阈值）。新鲜度检查是被坑出来的：semianalysis.com/feed 和 qwenlm.github.io feed 都是"HTTP 200 但停更 9 个月"的僵尸。
- **降噪声明在源上**：`exclude_pattern` 过滤 RC/alpha/CI tag。llama.cpp 每次 CI build 发 release、PyTorch 的 atom 里全是 trunk/<sha>——这类源要么换端点（PyPI feed）要么带过滤，否则 digest 会被刷屏。
- **probe/doctor 是只读的**（`DIFF_DRY_RUN`）：验证工具不许推进 diff 快照，否则一次冒烟测试就会偷吃当天的增量。
- 已知坑统一记录在 [`asta-news/sources/_schema.md`](../asta-news/sources/_schema.md) 的坑表——加源先查表。

## 五、状态目录一览

```
~/.claude/plugins/data/asta-news/     # plugin 升级不影响（CLAUDE_PLUGIN_DATA / ASTA_NEWS_HOME）
├── sources.local.yaml    # 个人源（同 id 覆盖默认表）
├── rules.local.yaml      # 个人规则（递归深合并进 rules.yaml）
├── profile.md            # 编辑画像：人写区随便改；机器只动 ASTA:STATS 标记之间
├── seen.db               # 去重库（14 天滑窗）
├── runs/<date>/          # 当日中间产物（candidates/fresh/manifest/分组切片）
├── runs/state/           # diff 型源的快照
├── archive/<date>.md     # digest 归档 = 已推送台账
└── rsshub/               # RSSHub compose + .env（凭证在此）
```

## 六、运行模型

plugin 不内置调度。任何调度器（cron / launchd / Claude Code routines / 有人手动）启动一个 Claude Code agent 执行 `/asta-news:daily-digest` 即可。两道防呆：调度声明的预期时间晚 2 小时以上 → 声明过期跳过（不补发旧闻）；当天 archive 已存在 → 不重发。

## 六·补：检索（混合 BM25 + 向量，RRF 融合）

"搜一条新闻 / 找相关"不只是关键词。`scripts/search.py` 把两路检索用 RRF（Reciprocal Rank Fusion）融合：

- **BM25 关键词**（rank-bm25，中文走 jieba 分词，TF-IDF + 长度归一）：命名实体/术语查询（模型名、论文标题）的精确命中。
- **向量语义**（fastembed 跨语言索引，与 embedding 同模型）：换语言、换说法也能召回。
- **RRF**：每路只取排名、按 1/(k+rank) 相加——免去 BM25 分数与余弦量纲不一致的调参，比线性加权稳。

服务端 `services/app.py /api/search` 用它（本地/全功能模式，已端到端验证）；静态 Pages 站用浏览器内向量搜（transformers.js 同款模型 + 预构建 `vectors.bin`，渐进增强）。任一路不可用（如 fastembed 缺失）优雅退化为单路。相关新闻是构建期预计算的 top-K 近邻（`related.json`），静态可用、无需浏览器模型。

## 七、这套设计从哪来

构建前评估了 5 个 arXiv-digest 项目（ArxivDigest / customize-arxiv-daily / daily-arXiv-ai-enhanced / llm-arxiv-daily / daily-ai-papers）、openclaw-newsroom、anthropics/skills 与 claude-code 官方 plugin 范例，以及一个早期内部实现；98 个源全部逐一实测（probe 通过日期记录在每个条目的 `verified` 字段）。"继承什么 / 避开什么"的完整清单见 `research/`，实施计划见 [`docs/superpowers/plans/2026-06-12-asta-news-plugin.md`](superpowers/plans/2026-06-12-asta-news-plugin.md)。
