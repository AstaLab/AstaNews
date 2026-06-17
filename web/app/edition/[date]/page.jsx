import { allDates, getEdition } from "../../../lib/data";
import EditionView from "../../../components/EditionView";
import Link from "next/link";

export function generateStaticParams() {
  return allDates().map((date) => ({ date }));
}

export async function generateMetadata({ params }) {
  const { date } = await params;
  const ed = getEdition(date);
  if (!ed) return { title: "AstaNews" };
  const title = `${ed.headline || "AI 全栈每日情报"} · ${date} · AstaNews`;
  const desc = (ed.overview || "").slice(0, 150);
  const lead = (ed.tiers?.group || ed.selected || [])[0]?.image?.url;
  return {
    title, description: desc,
    openGraph: { title, description: desc, type: "article", images: lead ? [lead] : [] },
    twitter: { card: lead ? "summary_large_image" : "summary", title, description: desc, images: lead ? [lead] : [] },
  };
}

export default async function EditionPage({ params }) {
  const { date } = await params;
  const ed = getEdition(date);
  if (!ed) return <p className="empty">未找到 {date} 这期。</p>;
  const dates = allDates(); // 新→旧
  const i = dates.indexOf(date);
  const newer = i > 0 ? dates[i - 1] : null;   // 更新的一期
  const older = i >= 0 && i < dates.length - 1 ? dates[i + 1] : null; // 更旧的一期
  return (
    <>
      <div className="dateline">往期</div>
      <h1 className="ed-headline">{ed.date}<span className="wd">{ed.weekday ? ` · ${ed.weekday}` : ""}</span></h1>
      {ed.overview && <p className="ed-abstract">{ed.overview}</p>}
      <EditionView edition={ed} />
      <nav style={{ marginTop: 34, paddingTop: 16, borderTop: "1px solid var(--rule)", display: "flex", justifyContent: "space-between", fontFamily: "var(--mono)", fontSize: 13 }}>
        <span>{older ? <Link href={`/edition/${older}`}>← {older}</Link> : <span style={{ color: "var(--faint)" }}>没有更早</span>}</span>
        <Link href="/archive" style={{ color: "var(--muted)" }}>往期目录</Link>
        <span>{newer ? <Link href={`/edition/${newer}`}>{newer} →</Link> : <span style={{ color: "var(--faint)" }}>已是最新</span>}</span>
      </nav>
    </>
  );
}
