---
name: daily-digest
description: 生成当日 AI 全栈 digest（日报）。当用户要求"跑今天的 digest / 日报 / AI 新闻推送 / asta news / 今天有什么值得看的 AI 进展"，或由定时任务触发每日情报汇总时使用。覆盖论文、模型发布、评测、infra/serving、MaaS、agent、具身、安全、产品商业、devtool 共 13 层，产出默认 5 条（最多 8 条、≥3 层）的策展结果。
---

# Daily Digest 工作流

你是 AstaNews 的主编。目标：从全栈数据源中选出**今天真正值得 Asta Lab 成员花 30 秒读的 5 条**（上限 8 条），而不是罗列新闻。质量不足宁可少发。

脚本都是黑盒：先 `--help`，不要读源码。两个目录：

- `$DATA`（运行态/中间产物）：`${CLAUDE_PLUGIN_DATA}`，env `ASTA_NEWS_HOME` 优先。candidates/fresh/分组切片放这，可丢可重建。
- `$OUT`（最终产物，要进 git）：env `ASTA_OUTPUT_DIR`，未设则用 plugin 旁的 `site/`。**digest 的网页数据与归档发布到这里**——仓库就是部署单元，GitHub Actions 跑完 commit `$OUT/data` + `$OUT/../editions` 即触发 Pages 更新。

**两种运行模式**（影响去重与登记）：
- **仓库模式**（GitHub Actions，或本地对着 clone 跑）：去重用"仓库即状态"——读 `$OUT/data/` 历史 digest.json，不依赖本地 db。无需单独登记，产物 commit 后即是下次的状态。
- **本地交互模式**：去重用 `$DATA/seen.db`，发布后 `dedup.py --record` 登记。
判断：`$OUT/data/` 存在且有历史 json → 仓库模式；否则本地模式。

## 0. 过期检查

读 `${CLAUDE_PLUGIN_ROOT}/rules.yaml`，再用 `$DATA/rules.local.yaml` 做递归深合并（嵌套键逐层覆盖，本地优先）——后续步骤用的都是合并结果。

过期判断：**只有当触发本次运行的指令里明确带了预期执行时间/日期**（外部调度通常会写，如"跑 2026-06-11 的日报"）且距现在超过 `edition.staleness_skip_hours` 小时，才输出一行声明并结束，不补发旧闻：

> ⏰ AstaNews {预期日期} 已过期跳过（当前 {now}）。

指令没带预期时间就视为准点，直接继续。若 `$DATA/archive/{YYYY-MM-DD}.md`（今天）已存在，说明今天已发过——告知用户并停止，除非用户明确要求重跑。

## 1. 抓取

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_sources.py --window-hours <rules 的 scoring.window_hours>
```

- **后续路径一律以 stderr 末尾打印的 `candidates ->` / `manifest ->` 实际路径为准**，不要自己拼日期目录。
- 退出码 1（零候选，周末常见）：跳到第 5 步，发"今日无足够增量"的简报。
- 读 stderr 汇总与 manifest：记下**失败的源**和 **agent_read 的 html 源**。
- html 源（Anthropic alignment、PI、Figure、DeepSeek updates 等）：挑 P0/P1 的 3-6 个，并行 WebFetch 它们的索引页（manifest 里 `needs_proxy` 的源若直连失败，提示用户检查 ASTA_PROXY），看窗口内有没有新文章；有就手动补成候选行追加进 candidates 文件，字段对齐其他行：`{"id": "<source_id>:manual-<序号>", "source": "<source_id>", "layers": [...], "title": "...", "url": "...", "published": "<ISO8601>", "summary": "...", "extra": {}}`。

## 2. 去重

```bash
# 仓库模式（推荐 / GitHub Actions）：仓库即状态
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/dedup.py --filter <candidates 路径> --seen-from $OUT/data
# 本地交互模式：用 seen.db
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/dedup.py --filter <candidates 路径>
```

产出 `fresh.jsonl`。同时读 `$OUT/data/` 最近 3 天的 digest.json 标题——editor 裁决时避免报道"同一事件的后续碎片"。

## 3. 并行富化评分（subagent fan-out）

读 `references/curation.md` 拿评分 rubric 与 prompt 模板，然后把 fresh 候选按 layer 分 3-5 组（如 papers / releases+maas / infra+serving+eval / agent+devtool / 其他），**每组派一个 subagent 并行**处理：

- 输入：该组候选（含 title/url/summary/extra）+ rubric + `$DATA/profile.md` 的兴趣与负向兴趣。
- 任务：粗筛掉明显无关项后，对幸存者**逐条**（不要批量打一个分数列表，防致幻）按 4 维打分（novelty / leading_edge / impact / cross_stack，各 0-5），必要时 WebFetch 原文核实；每条给一句**事实依据**（含至少一个量化点，只许用原文已述内容，不确定要写明）。
- 输出 JSON 的字段以 `references/curation.md` 的 prompt 模板为准（含 drop/scores/fact/recommend/primary_url）；加权分由你在裁决时按 weights 计算，不让 subagent 算。
- **评分失败/拿不准 = recommend false**，绝不默认高分。收到结果后核对返回 id 都在输入集合内，多出的丢弃。

每个 subagent 限处理 ≤40 条；候选过多时先按源优先级（P0 优先）与 extra 热度信号（upvotes/points/stars）截断。

## 4. Editor 裁决 → 信息很全的结构化记录

汇总各组推荐，按 `references/curation.md` 的 editor 准则做最终选择：

1. 负向兴趣（profile.md）一票否决。
2. 同一事件多条 → 合并为一条，链接用官方一手源，社区讨论（HN/HF）作附注。
3. 按 `scoring.weights` 加权分排序，选 `edition.default_items` 条（质量不足可更少；硬上限 `max_items`）。
4. 校验约束：覆盖 ≥ `min_layers` 层、单层 ≤ `max_per_layer`、单源 ≤ `max_per_source`。不满足就用次优候选替换补足；补不足层数时减条数也要保住多样性。
5. 落选但接近的 3-5 条放进"雷达"。

**多级筛选**（读 `${CLAUDE_PLUGIN_ROOT}/config/tiers.yaml`）：一次评分，切三层。
- `group`（群聊级，~5/上限 8，最严）= 上面选出的精选。
- `daily`（日报级，目标 ~20）= 在 group 之上放宽（score_threshold 更低、min_layers≥6、单层≤4、单源≤3），按分数补足到 ~20，覆盖更多 layer 与长尾。**daily 必须包含全部 group 条目**。
- `full` = 全部候选（all_candidates）。

对每个 group 与 daily 条目整理**信息很全**的记录（下一步改写的输入，facts 越全越不会写错）：
`{id, rank, layer, source, title（忠实转述）, facts:[尽量全的量化点], why_matters, links:{primary, discussion}, scores, source_excerpt（原文摘要/正文截断 ~400 字，供网页"深读"展示）}`。

## 5. Readiness 改写（独立 subagent）

提取与改写分开做——派 subagent，喂它**上一步的完整记录** + `references/readiness.md`，产出面向微信群跨栈受众的稿子：
- `group` 条目：完整 `readable`（新闻体 3-4 段，见 readiness.md）。
- `daily` 中非 group 的条目：精简 `take`（2-3 句新闻体短评，含量化点）——日报量大，不必每条 3-4 段。
- 整期的 `headline` 与 `overview`。
- 各视角的一句导语（读 `${CLAUDE_PLUGIN_ROOT}/config/perspectives.yaml`，按当天 daily 内容点名该视角下最值得看的 1-2 条）。
要点全在 readiness.md：先桥接"关你什么事"、保留技术锚点并解释、诚实标注保留、不丢任何数字。改写不改事实，只重写表达，不新增、不脑补。

## 6. 产出 digest.json + 归档 + 发布站点

组装 `digest.json`（schema v2，见 `references/output-format.md`）：
- `tiers`: `{group:[...], daily:[...], full:[...]}`（full = all_candidates 降维 `{source,layer,title,url,summary,selected}`，summary 截断 ~240 字）。
- `perspectives`: `{technical:{lede},product:{lede},business:{lede},research:{lede},embodied:{lede}}`（视角重排在前端按 perspectives.yaml 权重做，这里只给导语）。
- 顶层 `selected` = tiers.group、`all_candidates` = tiers.full（向后兼容旧消费者）。
- `schema_version: 2`。
写到 run 目录后，先配图再发布：

```bash
# 配图（橘鸦式"用图说话"：og:image / GitHub 社交预览 / HF 卡图；抓不到则前端用 layer 色兜底）
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/enrich_images.py --edition $DATA/runs/<today>/digest.json --tiers group,daily || true
# 一步发布：写 $OUT/data/<date>.json + 重建 index.json + 生成 $OUT/../editions/<date>.md（微信版用 group）
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/publish_site.py --digest $DATA/runs/<today>/digest.json --site-dir $OUT
# 重建向量索引（语义检索用；hf-mirror 自动）
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/embed.py --build $OUT/data || echo "embed 失败不阻塞"
# 仅本地交互模式额外登记去重库（仓库模式无需——commit 后的 digest.json 即状态）
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/dedup.py --record <选中+雷达条目.jsonl> --status published
```

publish_site 一次产出网页数据和微信归档，json 是唯一事实源、md 由它生成不漂移。最后在会话里**完整输出 digest 全文**（微信版），附一行运行摘要（N 源成功/M 失败、候选数）。抓取失败的源如实列在"数据缺口"——缺什么要说，这是可信度的一部分。

GitHub Actions 模式下，commit `$OUT/data` 与 `$OUT/../editions` 由 workflow 负责，skill 只管把产物写到位。

## 失败处置

- 单源失败：继续，列入数据缺口。
- fetch 全失败 / 网络瘫痪：输出诊断建议（`uv run …/scripts/doctor.py`），不要硬编一期 digest。
- 候选不足 5 条但有 2-3 条真货：照发，注明"今日从简"。
