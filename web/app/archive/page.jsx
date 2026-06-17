import Link from "next/link";
import { editionIndex } from "../../lib/data";
import { layerName } from "../../lib/config";

export const metadata = { title: "往期 · AstaNews" };

export default function Archive() {
  const eds = editionIndex();
  return (
    <>
      <div className="dateline">往期归档 · {eds.length} 期</div>
      {eds.length === 0 ? <p className="empty">暂无归档</p> : (
        <ul className="issues">
          {eds.map((e, i) => (
            <li key={e.date}>
              <Link className="issue-row" href={`/edition/${e.date}`}>
                <div className="d">{e.date}{e.weekday ? ` · ${e.weekday}` : ""}</div>
                <div className="h">{e.headline || "AI 全栈每日情报"}</div>
                <div className="o">{e.overview}</div>
                <div className="m">No.{String(eds.length - i).padStart(3, "0")} · {(e.layers || []).map(layerName).join(" / ")}</div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
