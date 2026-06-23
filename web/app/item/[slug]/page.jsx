import Link from "next/link";
import { allItems, getItem } from "../../../lib/data";
import { layerName, layerEmoji } from "../../../lib/config";
import Img from "../../../components/Img";

export function generateStaticParams() {
  const slugs = Object.keys(allItems());
  // output: export 要求动态路由至少产出一个 param；无条目时用占位（页面会渲染"未找到"空态）。
  return slugs.length ? slugs.map((slug) => ({ slug })) : [{ slug: "none" }];
}

export async function generateMetadata({ params }) {
  const { slug } = await params;
  const it = getItem(slug);
  if (!it) return { title: "AstaNews" };
  const desc = (it.readable || it.take || "").split("\n\n")[0].slice(0, 140);
  return {
    title: `${it.title} · AstaNews`,
    description: desc,
    openGraph: { title: it.title, description: desc, type: "article", images: it.image?.url ? [it.image.url] : [] },
    twitter: { card: it.image?.url ? "summary_large_image" : "summary", title: it.title, description: desc, images: it.image?.url ? [it.image.url] : [] },
  };
}

export default async function ItemPage({ params }) {
  const { slug } = await params;
  const it = getItem(slug);
  if (!it) return <p className="empty">未找到该条目。</p>;
  const body = it.deep || it.readable || it.take || ""; // 详情页正文 = 深读全文解读（比列表摘要更深）
  const rel = (it.related || []).filter((r) => r.score >= 0.3).slice(0, 6);
  return (
    <article>
      <div className="dateline">
        {it.date} · {layerEmoji(it.layer)} {layerName(it.layer)}
        <Link href={`/edition/${it.date}`} style={{ marginLeft: "auto", fontFamily: "var(--mono)", fontSize: 12 }}>← 本期</Link>
      </div>
      <h1 className="ed-title" style={{ fontFamily: "var(--cn-serif)", fontSize: "clamp(24px,3.4vw,34px)", lineHeight: 1.25, margin: "8px 0 16px" }}>{it.title}</h1>
      {it.image?.url && <Img className="thumb" src={it.image.url} alt="" style={{ width: "100%", borderRadius: 10, border: "1px solid var(--rule)", marginBottom: 18 }} />}
      {body && <div className="body" style={{ fontSize: 16, whiteSpace: "pre-wrap", color: "var(--ink-2)" }}>{body}</div>}
      <div className="links" style={{ marginTop: 18 }}>
        {it.links?.primary && <a href={it.links.primary} target="_blank" rel="noopener">一手源</a>}
        {it.links?.discussion && <a href={it.links.discussion} target="_blank" rel="noopener">讨论</a>}
      </div>
      {rel.length > 0 && (
        <>
          <div className="sec" style={{ marginTop: 36 }}>相关</div>
          <ul className="rows">
            {rel.map((r) => (
              <li className="row" key={r.url}>
                <div className="rhead">
                  <span className="lb">{r.date} · {layerName(r.layer)}</span>
                  <a href={r.url} target="_blank" rel="noopener">{r.title}</a>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </article>
  );
}
