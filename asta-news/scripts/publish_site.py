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
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SITE = PLUGIN_ROOT.parent / "site"


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
    args = ap.parse_args()

    data_dir = Path(args.site_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if args.rebuild_index and not args.digest:
        rebuild_index(data_dir)
        return 0

    if not args.digest:
        print("需要 --digest 或 --rebuild-index", file=sys.stderr)
        return 2

    digest = json.loads(Path(args.digest).read_text())
    errs = validate(digest)
    if errs:
        print("digest.json 校验失败：\n  " + "\n  ".join(errs), file=sys.stderr)
        return 2

    date = digest["date"]
    out = data_dir / f"{date}.json"
    out.write_text(json.dumps(digest, ensure_ascii=False, indent=1))
    print(f"发布 {date}：精选 {len(digest.get('selected', []))} 条 -> {out}", file=sys.stderr)
    rebuild_index(data_dir)
    print(f"\n站点目录 {args.site_dir} 已更新。本地预览：\n"
          f"  cd {args.site_dir} && python3 -m http.server 8000  # 然后访问 http://localhost:8000",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
