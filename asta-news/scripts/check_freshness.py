# /// script
# requires-python = ">=3.10"
# ///
"""asta-news 新鲜度审计：盯"本体"是否真的新，而不是"别人今天才转载"。

媒体常在论文/模型出来几周后才写、二次综述把旧发布当头条——recent coverage ≠ fresh
subject。本脚本对 digest 的 **每一条** group/daily 都判本体发生日，信号优先级：

  1. it.subject_date（editor 落库的本体发生日，ISO；最权威）
  2. URL 内嵌日期（techcrunch /2026/06/20/、simonwillison /2026/Jun/21/ 等可靠永久链接）
  3. arXiv ID 月份（YYMM.NNNNN → 该月【月末】，最宽松，只能判跨月陈旧）

判定：
  - 给了 --window-start（=本期窗口起点，通常是上一期 generated_at）时，**精确**本体日
    （来源 1/2）早于窗口起点即 STALE（窗口外即旧，贴合"窗口=上一期→现在"铁律）。
  - 没给 --window-start，或只有 arXiv 月末这种不精确日期时，回退到"本体日距今 > max_age_days"。
  - 本体日**完全判不出**（三种信号都没有）→ 进 UNKNOWN，按"不确定即旧、宁缺毋滥"阻断。

退出码: 0=全新鲜  3=发现陈旧本体  4=有条目本体日不可判定（需补 subject_date 或剔除）  2=用法错
（3 与 4 同时存在时取较严的 3，但仍打印 UNKNOWN 明细。）

用法:
  check_freshness.py --edition digest.json [--window-start 2026-06-17T01:49Z] [--max-age-days 14] [--now 2026-06-22]
  check_freshness.py --self-test
"""
import argparse
import calendar
import json
import re
import sys
from datetime import date, datetime, timezone

ARXIV_RE = re.compile(r"\b(\d{2})(\d{2})\.\d{4,5}\b")  # YYMM.NNNNN（arXiv 新式 ID）
URL_DATE_NUM = re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})(?:[/?#]|$)")        # /2026/06/20/
URL_DATE_MON = re.compile(r"/(\d{4})/([A-Za-z]{3,9})/(\d{1,2})(?:[/?#]|$)")  # /2026/Jun/21/
_MONTHS = {m.lower(): i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_iso_date(s) -> date | None:
    """宽松解析 ISO 日期/日期时间（含末尾 Z）→ date；失败返回 None。"""
    if not s:
        return None
    s = str(s).strip()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


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


def url_subject_date(url: str) -> date | None:
    """从永久链接路径抽发布日（/YYYY/MM/DD/ 或 /YYYY/Mon/DD/）。"""
    if not url:
        return None
    m = URL_DATE_NUM.search(url)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = URL_DATE_MON.search(url)
    if m:
        mon = _MONTHS.get(m.group(2)[:3].lower())
        if mon:
            try:
                return date(int(m.group(1)), mon, int(m.group(3)))
            except ValueError:
                return None
    return None


def parse_subject_date(it: dict) -> tuple[date | None, str, bool]:
    """返回 (本体日, 依据, 是否精确)。精确=来自 subject_date 或 URL 内嵌日期（可与窗口起点逐日比较）；
    不精确=arXiv 月末（只能判跨月陈旧）。三种都没有 → (None, 'none', False)。"""
    # 1. editor 落库的本体发生日（最权威）
    for src in (it.get("subject_date"), (it.get("extra") or {}).get("subject_date")):
        d = parse_iso_date(src)
        if d:
            return d, "subject_date", True
    links = it.get("links") or {}
    urls = [links.get("primary"), links.get("discussion"), it.get("url")]
    # 2. URL 内嵌日期
    for u in urls:
        d = url_subject_date(u or "")
        if d:
            return d, "url-date", True
    # 3. arXiv 月末（不精确）
    for u in urls + [(it.get("extra") or {}).get("arxiv_id")]:
        d = arxiv_subject_end(u or "")
        if d:
            return d, "arxiv-month", False
    return None, "none", False


def audit(digest: dict, now: date, max_age_days: int,
          window_start: date | None = None) -> tuple[list[dict], list[dict]]:
    """返回 (stale, unknown)。stale=本体陈旧；unknown=本体日判不出。"""
    tiers = digest.get("tiers", {})
    seen, stale, unknown = set(), [], []
    for tier in ("group", "daily"):
        for it in tiers.get(tier, []):
            key = (it.get("links") or {}).get("primary") or it.get("url") or it.get("title")
            if key in seen:
                continue
            seen.add(key)
            d, basis, precise = parse_subject_date(it)
            rec = {"tier": tier, "title": it.get("title", ""), "source": it.get("source", ""),
                   "url": (it.get("links") or {}).get("primary") or it.get("url"), "basis": basis}
            if d is None:
                unknown.append(rec)
                continue
            rec["subject_date"] = d.isoformat()
            if precise and window_start is not None:
                if d < window_start:
                    rec["why"] = f"本体日 {d} 早于窗口起点 {window_start}（窗口外）"
                    stale.append(rec)
            else:
                age = (now - d).days
                if age > max_age_days:
                    rec["age_days"] = age
                    rec["why"] = f"本体日 {d}（{basis}）距今 ~{age}d > {max_age_days}d"
                    stale.append(rec)
    return stale, unknown


def self_test() -> int:
    ok = True

    def item(title, primary=None, subject_date=None, source=""):
        it = {"title": title, "source": source, "links": {"primary": primary}}
        if subject_date:
            it["subject_date"] = subject_date
        return it

    # 用例 A：window-start 精确判定（窗口起点 06-17，now 06-22）
    ws = date(2026, 6, 17)
    dgA = {"tiers": {"group": [
        item("GLM-5.2（引 latent.space 二次综述）", "https://www.latent.space/p/ainews-glm",
             subject_date="2026-06-16"),                                   # 早于窗口 → stale
        item("John Jumper 离开 DeepMind", "https://techcrunch.com/2026/06/20/jumper/"),  # url 06-20 → fresh
        item("MosaicLeaks", "https://huggingface.co/blog/mosaicleaks"),    # 无任何日期 → unknown
    ]}}
    stA, unA = audit(dgA, date(2026, 6, 22), 14, ws)
    a_ok = len(stA) == 1 and stA[0]["title"].startswith("GLM-5.2") and len(unA) == 1
    ok &= a_ok
    print(f"  [{'OK' if a_ok else 'FAIL'}] A: stale={len(stA)}(want1 GLM) unknown={len(unA)}(want1 blog)")

    # 用例 B：arXiv 月末回退（无 window-start，max-age=14，now 06-15）
    dgB = {"tiers": {"daily": [
        item("May 旧论文", "https://arxiv.org/abs/2605.20613"),   # 月末 05-31，age 15>14 → stale
        item("June 新论文", "https://arxiv.org/abs/2606.07297"),  # 月末 06-30 → fresh
    ]}}
    stB, unB = audit(dgB, date(2026, 6, 15), 14, None)
    b_ok = len(stB) == 1 and "May" in stB[0]["title"] and len(unB) == 0
    ok &= b_ok
    print(f"  [{'OK' if b_ok else 'FAIL'}] B: stale={len(stB)}(want1 May) unknown={len(unB)}(want0)")

    # 用例 C：全新鲜不误杀（都带窗口内 subject_date）
    dgC = {"tiers": {"group": [
        item("窗口内事件1", "https://x.com/a/status/1", subject_date="2026-06-19"),
        item("窗口内事件2", "https://simonwillison.net/2026/Jun/21/x/"),
    ]}}
    stC, unC = audit(dgC, date(2026, 6, 22), 14, ws)
    c_ok = len(stC) == 0 and len(unC) == 0
    ok &= c_ok
    print(f"  [{'OK' if c_ok else 'FAIL'}] C: stale={len(stC)}(want0) unknown={len(unC)}(want0)")

    print("self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edition")
    ap.add_argument("--window-start", help="本期窗口起点 ISO（=上一期 generated_at）；提供后精确本体日早于它即判旧")
    ap.add_argument("--max-age-days", type=int, default=14, help="无 window-start / 仅 arXiv 月末时的回退口径")
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
    window_start = parse_iso_date(args.window_start) if args.window_start else None
    digest = json.loads(open(args.edition).read())
    stale, unknown = audit(digest, now, args.max_age_days, window_start)

    for s in stale:
        print(f"  ⚠ STALE [{s['tier']}] {s['title'][:48]} — {s.get('why', '')} {s['url']}", file=sys.stderr)
    for u in unknown:
        print(f"  ? UNKNOWN [{u['tier']}] {u['title'][:48]} — 本体日判不出（source={u['source']}）{u['url']}",
              file=sys.stderr)

    if stale:
        msg = f"新鲜度审计：{len(stale)} 条本体陈旧（本体日早于窗口起点 / 超龄）——editor 应剔除或改挂更新的进展/一手源。"
        if unknown:
            msg += f" 另有 {len(unknown)} 条本体日不可判定，需补 subject_date 或剔除。"
        print(msg, file=sys.stderr)
        return 3
    if unknown:
        print(f"新鲜度审计：{len(unknown)} 条本体日不可判定（缺 subject_date / URL 无日期 / 非 arXiv）"
              f"——按宁缺毋滥需补准本体发生日或剔除，不得放行。", file=sys.stderr)
        return 4
    print("新鲜度审计通过：group/daily 全部条目本体日均在窗口内。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
