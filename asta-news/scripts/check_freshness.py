# /// script
# requires-python = ">=3.10"
# ///
"""asta-news 新鲜度审计：盯"本体"是否真的新，而不是"别人今天才转载"。

媒体常在论文出来几周后才写——recent coverage ≠ fresh subject。一手源是 arXiv 时，
其 ID 前缀就是提交年月（YYMM.NNNNN），据此可零抓取判断本体年龄：本体月份的月末都早于
(now − max_age_days) 的，判 STALE。供 editor 剔除 / CI 拦截，别让陈年论文当今日新闻。

扫 digest 的 group/daily 每条的 links.primary、links.discussion、url，及 extra.arxiv_id。
退出码: 0=全新鲜  3=发现陈旧本体（非零，便于 skill/CI 据此处理）  2=用法错

用法:
  check_freshness.py --edition digest.json [--max-age-days 14] [--now 2026-06-15]
  check_freshness.py --self-test
"""
import argparse
import calendar
import json
import re
import sys
from datetime import date, datetime, timezone

ARXIV_RE = re.compile(r"\b(\d{2})(\d{2})\.\d{4,5}\b")  # YYMM.NNNNN（arXiv 新式 ID）


def arxiv_subject_end(text: str) -> date | None:
    """从 URL/ID 抽 arXiv 提交月，返回该月【月末】（最宽松假设，避免误杀当月新论文）。"""
    m = ARXIV_RE.search(text or "")
    if not m:
        return None
    yy, mm = int(m.group(1)), int(m.group(2))
    if not (1 <= mm <= 12):
        return None
    year = 2000 + yy
    return date(year, mm, calendar.monthrange(year, mm)[1])


def item_subject_end(it: dict) -> date | None:
    links = it.get("links") or {}
    for u in (links.get("primary"), links.get("discussion"), it.get("url"),
              (it.get("extra") or {}).get("arxiv_id")):
        d = arxiv_subject_end(u or "")
        if d:
            return d
    return None


def audit(digest: dict, now: date, max_age_days: int) -> list[dict]:
    tiers = digest.get("tiers", {})
    seen, stale = set(), []
    for tier in ("group", "daily"):
        for it in tiers.get(tier, []):
            key = (it.get("links") or {}).get("primary") or it.get("url") or it.get("title")
            if key in seen:
                continue
            seen.add(key)
            end = item_subject_end(it)
            if end is None:
                continue  # 非 arXiv 本体（事件/发布/产品）：日期=报道日，不在此判
            age = (now - end).days
            if age > max_age_days:
                stale.append({"tier": tier, "title": it.get("title", ""),
                              "subject_month": end.strftime("%Y-%m"), "age_days": age,
                              "url": (it.get("links") or {}).get("primary") or it.get("url")})
    return stale


def self_test() -> int:
    now = date(2026, 6, 15)
    cases = [
        ("https://arxiv.org/abs/2605.23904", True),   # May → 旧
        ("https://arxiv.org/abs/2605.20613", True),   # May → 旧
        ("https://arxiv.org/abs/2606.07297", False),  # June → 新
        ("https://paperswithcode.co/paper/2606.13676", False),
        ("https://the-decoder.com/some-event/", False),  # 非 arXiv
    ]
    ok = True
    for url, want_stale in cases:
        end = arxiv_subject_end(url)
        got = end is not None and (now - end).days > 14
        flag = "OK" if got == want_stale else "FAIL"
        if got != want_stale:
            ok = False
        print(f"  [{flag}] {url} -> subject_end={end} stale={got} (want {want_stale})")
    print("self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edition")
    ap.add_argument("--max-age-days", type=int, default=14)
    ap.add_argument("--now", help="测试/补跑用，ISO 日期；默认今天")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.edition:
        print("用法错：需 --edition 或 --self-test", file=sys.stderr)
        return 2
    now = (datetime.fromisoformat(args.now).date() if args.now
           else datetime.now(timezone.utc).date())
    digest = json.loads(open(args.edition).read())
    stale = audit(digest, now, args.max_age_days)
    for s in stale:
        print(f"  ⚠ STALE [{s['tier']}] {s['title'][:52]} — arXiv {s['subject_month']} "
              f"(~{s['age_days']}d) {s['url']}", file=sys.stderr)
    if stale:
        print(f"新鲜度审计：{len(stale)} 条本体陈旧（本体月末早于 now−{args.max_age_days}d）"
              f"——editor 应剔除或换一手源/换更新的进展。", file=sys.stderr)
        return 3
    print("新鲜度审计通过：group/daily 无陈旧 arXiv 本体。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
