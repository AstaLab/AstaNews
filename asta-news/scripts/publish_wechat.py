# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown", "beautifulsoup4", "requests"]
# ///
"""把每日 digest 转成微信公众号可用的内联样式 HTML（橘鸦风），可选发布到公众号。

微信正文不认 class/外链 CSS，只认**内联 style**。本脚本：
  editions/<date>.md  →  python-markdown 转 HTML  →  逐元素打内联样式（米色卡片/朱砂标题/虚线分割/圆角图）
  →  写 <date>.wechat.html（草稿可预览/粘贴）；配 WECHAT_APPID/WECHAT_SECRET 则可直接发草稿。

用法:
  publish_wechat.py --md editions/2026-06-13.md            # 生成内联样式 HTML 预览
  publish_wechat.py --md editions/2026-06-13.md --publish   # 另调公众号 API 发草稿（需凭证）
"""
import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# 配色对齐站点 gazette / 橘鸦：暖米纸 + 朱砂橘
C = {"paper": "#f1ead9", "card": "#faf5ea", "ink": "#211c14", "ink2": "#433c2e",
     "seal": "#b23a23", "rule": "#d3c7ab", "muted": "#6a6150"}


def style_html(md_text: str) -> str:
    import markdown
    from bs4 import BeautifulSoup
    html = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
    soup = BeautifulSoup(html, "html.parser")

    def s(el, css):
        el["style"] = css

    for h1 in soup.find_all("h1"):
        s(h1, f"font-size:24px;font-weight:800;color:{C['seal']};text-align:center;margin:8px 0 18px;letter-spacing:.5px;")
    for h2 in soup.find_all("h2"):
        s(h2, f"font-size:19px;font-weight:700;color:{C['ink']};background:{C['card']};border-left:4px solid {C['seal']};"
              f"border-radius:8px;padding:10px 14px;margin:26px 0 12px;line-height:1.4;")
    for bq in soup.find_all("blockquote"):
        s(bq, f"background:{C['card']};border:1px solid {C['rule']};border-radius:10px;padding:12px 16px;"
              f"margin:14px 0;color:{C['ink2']};font-size:15px;line-height:1.7;")
        for p in bq.find_all("p"):
            s(p, "margin:0;")
    for p in soup.find_all("p"):
        if not p.get("style"):
            s(p, f"font-size:15.5px;line-height:1.85;color:{C['ink2']};margin:10px 0;")
    for hr in soup.find_all("hr"):
        s(hr, f"border:none;border-top:1px dashed {C['rule']};margin:24px 0;")
    for img in soup.find_all("img"):
        s(img, "max-width:100%;border-radius:10px;display:block;margin:14px auto;")
    for a in soup.find_all("a"):
        s(a, f"color:{C['seal']};text-decoration:none;")
    for li in soup.find_all("li"):
        s(li, f"font-size:15px;line-height:1.8;color:{C['ink2']};margin:4px 0;")
    for code in soup.find_all("code"):
        s(code, f"background:{C['paper']};border-radius:4px;padding:1px 5px;font-size:13px;color:{C['seal']};")
    inner = "".join(str(c) for c in soup.children)
    return f'<section style="background:{C["paper"]};padding:20px 18px;font-family:-apple-system,PingFang SC,sans-serif;">{inner}</section>'


def wechat_publish(html: str, title: str):
    """发草稿到公众号。需 WECHAT_APPID/WECHAT_SECRET，且服务器 IP 在公众号白名单。"""
    appid, secret = os.environ.get("WECHAT_APPID"), os.environ.get("WECHAT_SECRET")
    if not (appid and secret):
        print("未配 WECHAT_APPID/WECHAT_SECRET，跳过发布（仅生成 HTML 预览）。", file=sys.stderr)
        print("接入：access_token=GET /cgi-bin/token → draft.add(articles:[{title,content:html,...}]) "
              "→ freepublish.submit。封面 thumb_media_id 需先 media/uploadimg。", file=sys.stderr)
        return False
    import requests
    tok = requests.get("https://api.weixin.qq.com/cgi-bin/token",
                       params={"grant_type": "client_credential", "appid": appid, "secret": secret},
                       timeout=15).json().get("access_token")
    if not tok:
        print("取 access_token 失败（检查凭证/IP 白名单）", file=sys.stderr)
        return False
    r = requests.post(f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={tok}",
                      json={"articles": [{"title": title[:64], "author": "AstaNews",
                                          "content": html, "need_open_comment": 0}]}, timeout=20).json()
    ok = "media_id" in r
    print(f"草稿{'已创建 '+r['media_id'] if ok else '失败 '+str(r)}", file=sys.stderr)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--md", required=True, help="editions/<date>.md")
    ap.add_argument("--out", help="输出 html 路径，默认同目录 <date>.wechat.html")
    ap.add_argument("--publish", action="store_true", help="另发草稿到公众号（需凭证）")
    args = ap.parse_args()
    md_path = Path(args.md)
    md = md_path.read_text()
    html = style_html(md)
    out = Path(args.out) if args.out else md_path.with_suffix(".wechat.html")
    out.write_text(f"<!doctype html><meta charset=utf-8><body style='margin:0'>{html}</body>")
    title = md.splitlines()[0].lstrip("# ").strip() if md else "AstaNews"
    print(f"微信 HTML → {out}（{len(html)} 字节，{'≤' if len(html)<1_000_000 else '超'}1MB 限制）", file=sys.stderr)
    if args.publish:
        wechat_publish(html, title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
