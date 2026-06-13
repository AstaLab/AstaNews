# /// script
# requires-python = ">=3.10"
# dependencies = ["rank-bm25", "jieba", "numpy", "fastembed"]
# ///
"""asta-news 混合检索——BM25 关键词 + 向量语义，RRF 融合（不仅是关键词）。

设计 §3.5：关键词命中（BM25，TF-IDF + 长度归一，中文走 jieba 分词）与语义相似
（向量余弦，复用 fastembed 跨语言索引）各出一个排名，用 RRF（Reciprocal Rank
Fusion）融合——免去两种分数量纲不一致的调参，对"搜一个模型名/概念都能找到对的那条"
更稳。语料是 site/data 各期候选的 标题+正文（readable/take/summary）。

退化：向量索引缺失 → 退 BM25-only；jieba/bm25 不可用 → 退向量-only。
服务端（services/app.py /api/search）调 hybrid_search；静态站仍用浏览器内向量搜。

用法:
  search.py --query "块级稀疏注意力" [--data site/data] [--top 10]
  search.py --self-test         # BM25 分词/排序 + RRF 融合（离线、无模型下载）
"""
import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

_WORD = re.compile(r"[0-9a-zA-Z一-鿿]+")


def tokenize(text: str) -> list[str]:
    """中英混合分词：jieba 切中文、保留英文/数字 token，小写、去标点空白。"""
    if not text:
        return []
    try:
        import jieba
        toks = jieba.lcut(text.lower())
    except Exception:
        toks = text.lower().split()
    out = []
    for t in toks:
        t = t.strip()
        if t and _WORD.match(t):
            out.append(t)
    return out


def load_corpus(data_dir: Path) -> list[dict]:
    """复用 embed.iter_candidates 收集 {id(url), title, text}（与向量索引同身份键）。"""
    import embed
    return [{"id": c["id"], "title": c["title"], "url": c["url"], "date": c["date"],
             "layer": c["layer"], "selected": c["selected"], "text": c["text"]}
            for c in embed.iter_candidates(data_dir)]


def build_bm25(docs: list[dict]):
    from rank_bm25 import BM25Okapi
    corpus = [tokenize(f"{d['title']} {d.get('text','')}") for d in docs]
    return BM25Okapi(corpus)


def _rank_ids(scored: list[tuple]) -> dict:
    """[(id, score)…] 按分降序 → {id: rank}（rank 从 1 起）。"""
    order = sorted(scored, key=lambda x: -x[1])
    return {doc_id: i + 1 for i, (doc_id, _) in enumerate(order)}


def rrf_fuse(rank_maps: list[dict], k: int = 60) -> dict:
    """RRF：每个排名贡献 1/(k+rank)，跨榜相加。返回 {id: 融合分}。"""
    fused: dict = {}
    for rm in rank_maps:
        for doc_id, rank in rm.items():
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return fused


def hybrid_search(query: str, data_dir: Path, index_path: Path | None = None, top: int = 10) -> list[dict]:
    import embed
    docs = load_corpus(data_dir)
    by_id = {d["id"]: d for d in docs}
    rank_maps = []
    # BM25 关键词榜
    try:
        bm25 = build_bm25(docs)
        scores = bm25.get_scores(tokenize(query))
        rank_maps.append(_rank_ids([(docs[i]["id"], float(scores[i])) for i in range(len(docs))]))
    except Exception as e:
        print(f"  search: BM25 不可用，退化：{e}", file=sys.stderr)
    # 向量语义榜
    idx = index_path or embed.default_index()
    try:
        if Path(idx).exists():
            vecs, meta = embed.load_index(Path(idx))
            q = embed.embed([query])[0]
            vscores = vecs @ q
            rank_maps.append(_rank_ids([(meta[i]["id"], float(vscores[i])) for i in range(len(meta))]))
    except Exception as e:
        print(f"  search: 向量榜不可用，退化：{e}", file=sys.stderr)
    if not rank_maps:
        return []
    fused = rrf_fuse(rank_maps)
    ordered = sorted(fused.items(), key=lambda x: -x[1])[:top]
    out = []
    for doc_id, sc in ordered:
        d = by_id.get(doc_id, {"id": doc_id})
        out.append({"id": doc_id, "title": d.get("title", ""), "url": d.get("url", doc_id),
                    "date": d.get("date"), "layer": d.get("layer"), "selected": d.get("selected"),
                    "score": round(sc, 5)})
    return out


def cmd_self_test() -> int:
    # 1) 中英混合分词
    toks = tokenize("vLLM 投机解码 throughput 1.8x")
    assert "vllm" in toks and "投机" in toks and "throughput" in toks, f"分词异常：{toks}"
    print(f"  分词：{toks}")
    # 2) BM25 关键词排序：含查询词的文档应排第一
    docs = [
        {"id": "d1", "title": "块级稀疏注意力降低长上下文显存", "text": "MiniMax MSA block sparse attention"},
        {"id": "d2", "title": "新的多智能体编排框架", "text": "agent orchestration"},
        {"id": "d3", "title": "推理服务吞吐优化", "text": "serving throughput vLLM"},
    ]
    bm25 = build_bm25(docs)
    scores = bm25.get_scores(tokenize("块级稀疏注意力"))
    top_id = docs[max(range(len(docs)), key=lambda i: scores[i])]["id"]
    assert top_id == "d1", f"BM25 该把 d1 排第一，实得 {top_id}"
    print(f"  BM25：'块级稀疏注意力' → 命中 {top_id}（含该词的文档）")
    # 3) RRF 融合：两榜都靠前的文档应胜出
    bm_rank = {"d1": 1, "d2": 2, "d3": 3}
    vec_rank = {"d3": 1, "d1": 2, "d2": 3}
    fused = rrf_fuse([bm_rank, vec_rank])
    winner = max(fused, key=fused.get)
    assert winner == "d1", f"RRF 该选两榜都靠前的 d1，实得 {winner}"
    print(f"  RRF：bm榜#1+向量榜#2 的 d1 融合胜出（{ {k: round(v,4) for k,v in fused.items()} }）")
    print("self-test: 混合检索（分词/BM25/RRF）PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query")
    ap.add_argument("--data", default="site/data")
    ap.add_argument("--index")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return cmd_self_test()
    if not args.query:
        ap.error("需要 --query 或 --self-test")
    res = hybrid_search(args.query, Path(args.data), Path(args.index) if args.index else None, args.top)
    for r in res:
        star = "★" if r.get("selected") else " "
        print(f"{r['score']:.5f} {star} [{r['date']}] {r['title'][:64]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
