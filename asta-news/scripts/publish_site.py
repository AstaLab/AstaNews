# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""asta-news 站点发布器：把一天的 digest.json 发布到静态站点的 data/ 目录

digest.json 是 daily-digest skill 的结构化产物（精选 + 雷达 + 数据缺口 + 全量候选）。
本脚本把它拷进 site/data/<date>.json 并重建 site/data/index.json（站点首页据此列出归档）。
设计成 git hook 可调：digest 跑完 → publish_site.py → 提交 site/data/ → GitHub Pages 自动更新。

用法:
  publish_site.py --digest <run_dir>/digest.json          # 发布单日
  publish_site.py --digest digest.json --site-dir <dir>   # 自定义站点目录
  publish_site.py --rebuild-index                          # 仅按现有 data/*.json 重建 index
"""
import argparse
import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
# 产物落点优先级：--site-dir > $ASTA_OUTPUT_DIR > 仓库 site/（plugin 旁）
DEFAULT_SITE = Path(os.environ.get("ASTA_OUTPUT_DIR") or (PLUGIN_ROOT.parent / "site"))

LAYER_EMOJI = {
    "model": "🧠", "post-training": "🎛️", "eval": "📊", "data": "🗂️", "infra": "🏗️",
    "serving": "⚡", "maas": "☁️", "agent": "🤖", "embodied": "🦾", "safety": "🛡️",
    "product": "📦", "business": "💰", "devtool": "🔧",
}


def render_md(d: dict) -> str:
    """微信可读版 markdown（人看 / 直接粘群）。json 是唯一事实源，md 由它生成不会漂移。"""
    L = [f"# 🛰️ AstaNews — {d['date']}（{d.get('weekday','')}）", "", f"> {d.get('overview','')}", ""]
    for it in d.get("selected", []):
        L += [f"## {it.get('rank','')}. {LAYER_EMOJI.get(it['layer'],'')} [{it['layer']}] {it['title']}", "",
              it.get("readable", ""), ""]
        links = it.get("links", {})
        lk = [f"[一手源]({links['primary']})"] if links.get("primary") else []
        if links.get("discussion"):
            lk.append(f"[讨论]({links['discussion']})")
        if lk:
            L += ["🔗 " + " · ".join(lk), ""]
    if d.get("radar"):
        L += ["---", "", "### 📡 雷达", ""]
        for r in d["radar"]:
            tail = f" [↗]({r['link']})" if r.get("link") else ""
            L.append(f"- [{r['layer']}] {r['title']}{(' — ' + r['note']) if r.get('note') else ''}{tail}")
    if d.get("gaps"):
        L += ["", "### ⚠️ 数据缺口", ""] + [f"- {g}" for g in d["gaps"]]
    st = d.get("stats", {})
    L.append(f"\n*{len(d.get('selected',[]))} 条 · 覆盖 {' / '.join(st.get('layers_covered',[]))} · "
             f"候选 {st.get('candidates','—')} 条 · AstaNews*")
    return "\n".join(L)


def prune_full(data_dir: Path, keep_days: int) -> int:
    """瘦身：早于 keep_days 的 edition 只保留精选/雷达，删掉沉重的 all_candidates。
    日期比较用文件名（YYYY-MM-DD），不依赖运行时钟（GitHub Actions 友好、可复现）。"""
    import datetime
    dates = sorted(f.stem for f in data_dir.glob("20*.json") if f.name != "index.json")
    if len(dates) <= keep_days:
        return 0
    cutoff = dates[-keep_days]  # 保留最近 keep_days 期的全量
    pruned = 0
    for f in data_dir.glob("20*.json"):
        if f.name == "index.json" or f.stem >= cutoff:
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if d.get("all_candidates"):
            d["all_candidates"] = []
            d["pruned"] = True
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1))
            pruned += 1
    if pruned:
        print(f"瘦身：{pruned} 期早于 {cutoff} 的全量候选已清空（精选/雷达保留）", file=sys.stderr)
    return pruned


def rebuild_index(data_dir: Path) -> int:
    entries = []
    for f in sorted(data_dir.glob("20*.json"), reverse=True):
        if f.name == "index.json":
            continue
        try:
            d = json.loads(f.read_text())
        except json.JSONDecodeError:
            print(f"[跳过] {f.name} 解析失败", file=sys.stderr)
            continue
        entries.append({
            "date": d.get("date", f.stem),
            "overview": d.get("overview", ""),
            "selected": len(d.get("selected", [])),
            "layers": d.get("stats", {}).get("layers_covered", []),
            "candidates": d.get("stats", {}).get("candidates", 0),
        })
    index_path = data_dir / "index.json"
    index_path.write_text(json.dumps({"editions": entries}, ensure_ascii=False, indent=1))
    print(f"index.json 重建：{len(entries)} 期 -> {index_path}", file=sys.stderr)
    return len(entries)


def _normalize(digest: dict) -> None:
    """归一 tiers/selected 里每条的 facts(→list) 与 links(→dict)，容忍 agent 写串了的格式。"""
    def fix(it):
        fa = it.get("facts")
        if isinstance(fa, str):
            it["facts"] = [fa]
        elif fa is None:
            it["facts"] = []
        elif not isinstance(fa, list):
            it["facts"] = [str(fa)]
        lk = it.get("links")
        if isinstance(lk, str):
            it["links"] = {"primary": lk}
        elif not isinstance(lk, dict):
            it["links"] = {"primary": it.get("url", "")}
    for tier in ("group", "daily"):
        for it in digest.get("tiers", {}).get(tier, []):
            fix(it)
    for it in digest.get("selected", []):
        fix(it)


def validate(digest: dict) -> list[str]:
    """轻校验：站点渲染依赖这些字段"""
    errs = []
    if not digest.get("date"):
        errs.append("缺 date")
    for i, it in enumerate(digest.get("selected", [])):
        for k in ("title", "readable", "layer", "links"):
            if k not in it:
                errs.append(f"selected[{i}] 缺 {k}")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--digest", help="digest.json 路径")
    ap.add_argument("--site-dir", default=str(DEFAULT_SITE), help=f"站点根，默认 {DEFAULT_SITE}")
    ap.add_argument("--rebuild-index", action="store_true", help="仅重建 index.json")
    ap.add_argument("--prune-full-after", type=int, metavar="N",
                    help="把早于最近 N 期的 all_candidates 清空以瘦身（精选/雷达保留），然后重建 index")
    args = ap.parse_args()

    data_dir = Path(args.site_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if args.prune_full_after is not None and not args.digest:
        prune_full(data_dir, args.prune_full_after)
        rebuild_index(data_dir)
        return 0

    if args.rebuild_index and not args.digest:
        rebuild_index(data_dir)
        return 0

    if not args.digest:
        print("需要 --digest 或 --rebuild-index", file=sys.stderr)
        return 2

    digest = json.loads(Path(args.digest).read_text())
    _normalize(digest)  # 容错：把 agent 可能写错的 facts(字符串)/links(字符串) 归一，避免前端崩
    errs = validate(digest)
    if errs:
        print("digest.json 校验失败：\n  " + "\n  ".join(errs), file=sys.stderr)
        return 2

    date = digest["date"]
    out = data_dir / f"{date}.json"
    out.write_text(json.dumps(digest, ensure_ascii=False, indent=1))
    # 微信可读 md 落到仓库 editions/（site 的同级），供归档/直接粘群
    editions = Path(args.site_dir).parent / "editions"
    editions.mkdir(parents=True, exist_ok=True)
    md_path = editions / f"{date}.md"
    md_path.write_text(render_md(digest))
    print(f"发布 {date}：精选 {len(digest.get('selected', []))} 条\n"
          f"  网页数据 -> {out}\n  微信归档 -> {md_path}", file=sys.stderr)
    rebuild_index(data_dir)
    print(f"\n站点目录 {args.site_dir} 已更新。本地预览：\n"
          f"  cd {args.site_dir} && python3 -m http.server 8000", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
