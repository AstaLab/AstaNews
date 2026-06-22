# /// script
# requires-python = ">=3.10"
# dependencies = ["fastembed", "numpy"]
# ///
"""asta-news 本地 embedding + 向量检索（离线 CPU，不依赖 OpenAI）

多语模型 paraphrase-multilingual-MiniLM-L12-v2（384 维，zh+en 跨语言）。
索引为 npz（ids + float32 向量 + sidecar meta json）——语料不大时够用，
后续可平滑换 sqlite-vec/lancedb。混合检索的 BM25 部分在 search.py。

用法:
  embed.py --build site/data            # 扫所有 edition.json 的候选 → 建/更新索引
  embed.py --search "查询词" [--top 10]  # 向量检索
  embed.py --check fresh.jsonl          # 语义去重：和历史向量比对，高相似交 LLM 判断
  embed.py --self-test                  # 跨语言相似度自检
索引默认落 ${ASTA_INDEX:-<data>/vectors.npz}
语义去重阈值: --soft 0.72（标注+LLM）--hard 0.92（自动过滤）
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_model = None


def model():
    global _model
    if _model is None:
        # 默认走 hf-mirror（中国可直连，墙外也可达）；用户可用 HF_ENDPOINT 覆盖
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name=MODEL)
    return _model


def embed(texts: list[str]) -> np.ndarray:
    vecs = np.array(list(model().embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.clip(norms, 1e-9, None)  # L2 归一化 → 点积即余弦


def default_index() -> Path:
    if os.environ.get("ASTA_INDEX"):
        return Path(os.environ["ASTA_INDEX"])
    out = Path(os.environ.get("ASTA_OUTPUT_DIR", PLUGIN_ROOT.parent / "site"))
    return out / "data" / "vectors.npz"


def _lz(lay):
    return (lay[0] if isinstance(lay, list) else lay) or ""


def iter_candidates(data_dir: Path):
    """从所有 edition json 收集可检索条目，**以 URL 为统一身份**去重（前端按 url 查 related）。"""
    seen = set()
    for f in sorted(data_dir.glob("20*.json")):
        if f.name in ("index.json",):
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        date = d.get("date", f.stem)
        rows = []  # (url, title, body, layer, selected)
        tiers = d.get("tiers", {})
        for it in (tiers.get("group") or d.get("selected") or []):
            rows.append(((it.get("links") or {}).get("primary", ""), it.get("title", ""),
                         it.get("readable", "") or " ".join(it.get("facts", [])), _lz(it.get("layer")), True))
        for it in tiers.get("daily", []):
            rows.append(((it.get("links") or {}).get("primary", ""), it.get("title", ""),
                         it.get("take") or it.get("readable", ""), _lz(it.get("layer")), False))
        for c in (tiers.get("full") or d.get("all_candidates") or []):
            rows.append((c.get("url", ""), c.get("title", ""), c.get("summary", ""), _lz(c.get("layer")), False))
        for url, title, body, lay, sel in rows:
            if not url or url in seen:
                continue
            seen.add(url)
            yield {"id": url, "title": title, "text": f"{title}. {body}"[:512],
                   "url": url, "date": date, "selected": sel, "layer": lay}


def cmd_build(data_dir: Path, index_path: Path, top_k: int = 6) -> int:
    items = list(iter_candidates(data_dir))
    if not items:
        print("无可索引条目", file=sys.stderr)
        return 1
    vecs = embed([it["text"] for it in items])
    meta = [{k: it[k] for k in ("id", "title", "url", "date", "selected", "layer")} for it in items]
    np.savez_compressed(index_path, vectors=vecs, ids=np.array([m["id"] for m in meta]))
    index_path.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False))
    # 预计算"相关新闻"：每条的 top-K 语义近邻（排除自己与同 URL），静态可用、无需浏览器模型
    sims = vecs @ vecs.T
    related = {}
    for i, m in enumerate(meta):
        order = np.argsort(-sims[i])
        neigh = []
        for j in order:
            if j == i or meta[j]["url"] == m["url"]:
                continue
            neigh.append({"id": meta[j]["id"], "title": meta[j]["title"], "url": meta[j]["url"],
                          "date": meta[j]["date"], "layer": meta[j]["layer"], "score": round(float(sims[i][j]), 3)})
            if len(neigh) >= top_k:
                break
        related[m["id"]] = neigh
    (data_dir / "related.json").write_text(json.dumps(related, ensure_ascii=False))
    # 浏览器语义搜索用：Float32 行主序二进制 + 元数据（顺序对应）。
    # 浏览器用 transformers.js 同款模型(Xenova/paraphrase-multilingual-MiniLM-L12-v2)嵌入 query，点积即可。
    vecs.astype(np.float32).tofile(data_dir / "vectors.bin")
    (data_dir / "search.json").write_text(json.dumps({
        "model": "Xenova/paraphrase-multilingual-MiniLM-L12-v2",
        "dim": int(vecs.shape[1]), "count": len(meta),
        "items": [{"u": m["url"], "t": m["title"], "d": m["date"], "l": m["layer"]} for m in meta],
    }, ensure_ascii=False))
    print(f"索引 {len(items)} 条 → {index_path} ({vecs.shape[1]} 维) + related.json + vectors.bin/search.json（浏览器语义搜索）", file=sys.stderr)
    return 0


def load_index(index_path: Path):
    z = np.load(index_path, allow_pickle=False)
    meta = json.loads(index_path.with_suffix(".meta.json").read_text())
    return z["vectors"], meta


def search(query: str, index_path: Path, top: int = 10):
    vecs, meta = load_index(index_path)
    q = embed([query])[0]
    scores = vecs @ q
    order = np.argsort(-scores)[:top]
    return [{**meta[i], "score": float(scores[i])} for i in order]


def cmd_check(fresh_path: Path, index_path: Path, soft: float, hard: float) -> int:
    """语义去重：fresh 候选逐条和历史向量比对。
    - cosine >= hard → 自动标 semantic_dup（几乎相同的事件）
    - soft <= cosine < hard → 调 LLM 判断是"旧闻翻炒"还是"同领域新进展"
    LLM 不可用时退化为仅标注、不过滤（失败开放）。
    输出覆写原 fresh.jsonl，每条可能多出 semantic_similar / semantic_dup 字段。
    """
    vecs, meta = load_index(index_path)
    items = [json.loads(l) for l in fresh_path.read_text().splitlines() if l.strip()]
    if not items:
        print("无候选", file=sys.stderr)
        return 0
    texts = [f"{it.get('title','')}. {it.get('summary','')}"[:512] for it in items]
    qvecs = embed(texts)

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import llm

    from urllib.parse import urlsplit
    def _norm(u):
        p = urlsplit(u.strip())
        return (p.netloc.lower().removeprefix("www.") + p.path.rstrip("/")).lower()

    n_hard, n_llm_filter, n_llm_pass = 0, 0, 0
    for i, item in enumerate(items):
        scores = vecs @ qvecs[i]
        item_url = _norm(item.get("url", ""))
        top_idx = np.argsort(-scores)[:10]
        matches = []
        for j in top_idx:
            if _norm(meta[j].get("url", "")) == item_url:
                continue
            s = float(scores[j])
            if s < soft or np.isnan(s):
                break
            matches.append({
                "title": meta[j]["title"], "date": meta[j]["date"],
                "url": meta[j]["url"], "score": round(s, 3)
            })
            if len(matches) >= 3:
                break
        if not matches:
            continue
        item["semantic_similar"] = matches
        best = matches[0]["score"]

        if best >= hard:
            item["semantic_dup"] = True
            n_hard += 1
            print(f"  ✗ DUP  {best:.3f}  {item.get('title','')[:50]}", file=sys.stderr)
            print(f"         ↔ {matches[0]['title'][:50]} ({matches[0]['date']})", file=sys.stderr)
            continue

        # soft <= best < hard → LLM 判断
        if not llm.available():
            print(f"  ? SKIP {best:.3f}  {item.get('title','')[:50]}  (LLM 不可用，放行)", file=sys.stderr)
            continue

        verdict = llm.chat_json(
            "你是新闻去重判断器。判断候选新闻是否和已发布新闻是同一事件的重复/后续碎片。"
            "只返回 JSON: {\"dup\": true/false, \"reason\": \"一句话\"}",
            f"候选: {item.get('title','')} ({item.get('published','')})\n"
            f"  摘要: {item.get('summary','')[:300]}\n"
            f"已发布: {matches[0]['title']} ({matches[0]['date']})\n"
            f"语义相似度: {best:.3f}\n"
            f"判断: 候选是同一事件的旧闻/翻炒/后续评论吗? 还是同一领域但确实是新的不同事件/进展?"
        )
        if verdict and verdict.get("dup"):
            item["semantic_dup"] = True
            item["semantic_dup_reason"] = verdict.get("reason", "")
            n_llm_filter += 1
            print(f"  ✗ LLM  {best:.3f}  {item.get('title','')[:50]}  → {verdict.get('reason','')[:40]}", file=sys.stderr)
        else:
            n_llm_pass += 1
            reason = verdict.get("reason", "") if verdict else "LLM 返回异常，放行"
            print(f"  ✓ PASS {best:.3f}  {item.get('title','')[:50]}  → {reason[:40]}", file=sys.stderr)

    # 写回：过滤掉 semantic_dup=true 的条目，保留的带上 semantic_similar 标注
    kept = [it for it in items if not it.get("semantic_dup")]
    removed = len(items) - len(kept)
    with fresh_path.open("w") as f:
        for it in kept:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"语义去重: {len(items)} 候选 → 硬过滤 {n_hard} + LLM 过滤 {n_llm_filter} + LLM 放行 {n_llm_pass}"
          f" = 去除 {removed} 条 → {len(kept)} 条", file=sys.stderr)
    return 0


def cmd_self_test() -> int:
    pairs = [("开源编程模型", "open-source coding model"),
             ("块级稀疏注意力降低长文本显存", "block sparse attention reduces long-context memory")]
    neg = "今天天气不错适合散步"
    for zh, en in pairs:
        v = embed([zh, en, neg])
        sim_cross = float(v[0] @ v[1]); sim_neg = float(v[0] @ v[2])
        print(f"  '{zh}' ↔ '{en}' = {sim_cross:.3f}   vs 无关 = {sim_neg:.3f}")
        assert sim_cross > sim_neg + 0.15, "跨语言相似度未显著高于无关项"
    print("self-test: 跨语言相似检索 PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", metavar="DATA_DIR", help="扫该目录所有 edition json 建索引")
    g.add_argument("--search", metavar="QUERY")
    g.add_argument("--check", metavar="FRESH_JSONL",
                   help="语义去重：对 fresh 候选逐条比对历史向量，高相似交 LLM 判断")
    g.add_argument("--self-test", action="store_true")
    ap.add_argument("--index", default=str(default_index()))
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--soft", type=float, default=0.72,
                    help="语义软阈值：超过则标注 + 交 LLM 判断（默认 0.72）")
    ap.add_argument("--hard", type=float, default=0.92,
                    help="语义硬阈值：超过则自动过滤（默认 0.92）")
    args = ap.parse_args()
    idx = Path(args.index)
    if args.self_test:
        return cmd_self_test()
    if args.build:
        idx.parent.mkdir(parents=True, exist_ok=True)
        return cmd_build(Path(args.build), idx)
    if args.check:
        return cmd_check(Path(args.check), idx, args.soft, args.hard)
    for r in search(args.search, idx, args.top):
        star = "★" if r["selected"] else " "
        print(f"{r['score']:.3f} {star} [{r['date']}] {r['title'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
