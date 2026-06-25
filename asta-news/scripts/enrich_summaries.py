# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "pyyaml"]
# ///
"""批量补 summary：对 candidates.jsonl 中 summary 为空的条目，用小模型根据标题生成一句话简介。

并发调用 config/llm.yaml 配置的 OpenAI 兼容接口（DeepSeek / 通义 / ollama 等）。
LLM 不可用时退出码 1；单条失败跳过不影响整体。

用法:
  enrich_summaries.py --in candidates.jsonl [--out enriched.jsonl] [--workers 6]
  --in 与 --out 相同时原地更新。省略 --out 时默认原地。
"""
import argparse
import concurrent.futures as cf
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm  # noqa: E402

SYSTEM = (
    "你是新闻摘要生成器。给定一条 AI 领域新闻的标题和来源，"
    "用中文写一句话简介（15-40字），只说这条新闻讲了什么，不加评论。"
    '返回 JSON：{"summary": "..."}'
)


def enrich_one(item: dict) -> dict:
    title = item.get("title", "")
    source = item.get("source", "")
    url = item.get("url", "")
    prompt = f"标题：{title}\n来源：{source}\nURL：{url}"
    result = llm.chat_json(SYSTEM, prompt)
    if result and result.get("summary"):
        item["summary"] = result["summary"]
    return item


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", required=True, help="输入 candidates.jsonl")
    ap.add_argument("--out", dest="out", default=None, help="输出路径（默认原地更新）")
    ap.add_argument("--workers", type=int, default=6, help="并发数")
    args = ap.parse_args()

    if not llm.available():
        print("LLM 不可用（检查 config/llm.yaml + ASTA_LLM_KEY）", file=sys.stderr)
        return 1

    inp = Path(args.inp)
    items = [json.loads(line) for line in inp.read_text().splitlines() if line.strip()]
    need = [it for it in items if not it.get("summary")]
    print(f"共 {len(items)} 条，{len(need)} 条需补 summary", file=sys.stderr)

    if not need:
        print("全部已有 summary，无需补充", file=sys.stderr)
        return 0

    done, failed = 0, 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(enrich_one, it): it for it in need}
        for fut in cf.as_completed(futs):
            try:
                fut.result()
                done += 1
            except Exception as e:
                failed += 1
                print(f"  失败: {e}", file=sys.stderr)
            if (done + failed) % 20 == 0:
                print(f"  进度: {done + failed}/{len(need)}", file=sys.stderr)

    print(f"完成: {done} 成功, {failed} 失败", file=sys.stderr)

    out = Path(args.out) if args.out else inp
    with out.open("w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"写入 {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
