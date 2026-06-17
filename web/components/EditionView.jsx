"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { LAYERS, lz, layerName, layerEmoji, layerColor, TIERS, SHARPNESS, PERSPECTIVES, BASE, slug } from "../lib/config";

function Story({ it, n, related, lead, level }) {
  const body = (level === "deep" && it.deep) || (level === "sharp" && it.sharp) || it.readable || it.take || "";
  const facts = Array.isArray(it.facts) ? it.facts : it.facts ? [it.facts] : [];
  const links = [];
  if (it.links?.primary) links.push(["一手源", it.links.primary]);
  if (it.links?.discussion) links.push(["讨论", it.links.discussion]);
  const rel = (related?.[it.links?.primary] || []).filter((r) => r.score >= 0.35).slice(0, 3);
  return (
    <article className={lead ? "story lead" : "story"}>
      <div className="num">{n}</div>
      <div className="dept"><span>{layerEmoji(it.layer)}</span>{layerName(it.layer)}</div>
      <h2>{it.links?.primary ? <Link href={`/item/${slug(it.links.primary)}`}>{it.title}</Link> : it.title}</h2>
      {it.image?.url && <img className="thumb" src={it.image.url} alt="" loading="lazy" onError={(e) => { e.currentTarget.style.display = "none"; }} />}
      {body && <div className="body">{body}</div>}
      {facts.length > 0 && <ul className="facts">{facts.map((f, i) => <li key={i}>{f}</li>)}</ul>}
      {links.length > 0 && (
        <div className="links">{links.map(([t, u]) => <a key={u} href={u} target="_blank" rel="noopener">{t}</a>)}</div>
      )}
      {rel.length > 0 && (
        <div className="related">
          <span className="rel-label">相关</span>
          {rel.map((r) => (
            <a key={r.url} href={r.url} target="_blank" rel="noopener">
              <span className="rel-lb">{layerName(r.layer)}</span>{r.title}
            </a>
          ))}
        </div>
      )}
    </article>
  );
}

export default function EditionView({ edition }) {
  const [tier, setTier] = useState("daily");
  const [persp, setPersp] = useState("all");    // 视角（大）：软重排 + 导语
  const [cat, setCat] = useState("all");        // 类别（小）：按 layer 硬筛
  const [level, setLevel] = useState("neutral");  // 犀利度：中性 / 锐评 / 深读（按数据门控）
  const [related, setRelated] = useState(null); // 预计算的相关新闻（向量近邻）
  useEffect(() => {
    fetch(`${BASE}/data/related.json`).then((r) => r.json()).then(setRelated).catch(() => setRelated({}));
  }, []);
  const tiers = edition.tiers || { group: edition.selected || [], daily: edition.selected || [] };

  // 当前 tier 里出现的类别（只展示有内容的，按数量排序）
  const cats = useMemo(() => {
    const cnt = {};
    for (const it of tiers[tier] || []) { const k = lz(it.layer); if (k) cnt[k] = (cnt[k] || 0) + 1; }
    return Object.entries(cnt).sort((a, b) => b[1] - a[1]);
  }, [tier, edition.date]);

  const perspDef = PERSPECTIVES.find((p) => p.key === persp) || PERSPECTIVES[0];
  const perspLede = edition.perspectives?.[persp]?.lede || "";

  const items = useMemo(() => {
    let raw = tiers[tier] || [];
    if (cat !== "all") raw = raw.filter((it) => lz(it.layer) === cat);
    // 视角软重排：基础顺序分 + 该 layer 的 boost。稳定排序，不增删条目、不改事实。
    const boost = perspDef.boost || {};
    if (persp !== "all" && Object.keys(boost).length) {
      const n = raw.length;
      raw = raw
        .map((it, i) => ({ it, i, score: (n - i) + (boost[lz(it.layer)] || 0) * n }))
        .sort((a, b) => b.score - a.score || a.i - b.i)
        .map((x) => x.it);
    }
    return raw;
  }, [tier, cat, persp, edition.date]);

  // 当前 tier 有哪些犀利度档可选：中性恒在，锐评/深读需有对应数据（it.sharp / it.deep）
  const levels = useMemo(
    () => SHARPNESS.filter((l) => l.key === "neutral" || (tiers[tier] || []).some((it) => it[l.key])),
    [tier, edition.date]
  );
  const activeLevel = levels.some((l) => l.key === level) ? level : "neutral"; // 切 tier 后档位不可用则回退

  return (
    <div>
      <div className="controls">
        <div className="ctl-group">
          <span className="ctl-label">级别</span>
          <div className="seg">
            {TIERS.map((t) => (
              <button key={t.key} className={tier === t.key ? "on" : ""} onClick={() => setTier(t.key)} title={t.desc}>
                {t.label}<span style={{ opacity: .6, marginLeft: 5, fontSize: 11 }}>{(tiers[t.key] || []).length}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="ctl-group">
          <span className="ctl-label">视角</span>
          <div className="seg">
            {PERSPECTIVES.map((p) => (
              <button key={p.key} className={persp === p.key ? "on" : ""} onClick={() => setPersp(p.key)}>{p.label}</button>
            ))}
          </div>
        </div>
        {levels.length > 1 && (
          <div className="ctl-group">
            <span className="ctl-label">犀利度</span>
            <div className="seg">
              {levels.map((l) => (
                <button key={l.key} className={activeLevel === l.key ? "on" : ""} onClick={() => setLevel(l.key)}>{l.label}</button>
              ))}
            </div>
          </div>
        )}
      </div>

      {persp !== "all" && perspLede && (
        <p className="persp-lede"><span className="persp-tag">{perspDef.label}视角</span>{perspLede}</p>
      )}

      {/* 类别（小）：独立的 layer 硬筛 */}
      <div className="cats">
        <span className="ctl-label">类别</span>
        <button className={`chip ${cat === "all" ? "on" : ""}`} onClick={() => setCat("all")}>全部</button>
        {cats.map(([k, n]) => (
          <button key={k} className={`chip ${cat === k ? "on" : ""}`} onClick={() => setCat(cat === k ? "all" : k)}
            style={cat === k ? { background: layerColor(k), borderColor: layerColor(k), color: "#f4efe6" } : { borderColor: layerColor(k) + "66" }}>
            {layerEmoji(k)} {layerName(k)} <span style={{ opacity: .6 }}>{n}</span>
          </button>
        ))}
      </div>

      <div className="sec">
        {TIERS.find((t) => t.key === tier)?.label}
        {cat !== "all" ? ` · ${layerName(cat)}` : ""}
        <span style={{ fontFamily: "var(--mono)", color: "var(--faint)", marginLeft: 8 }}>{items.length}</span>
      </div>

      {items.length === 0
        ? <p className="empty">该类别下暂无条目。</p>
        : items.map((it, i) => <Story key={it.id || i} it={it} n={i + 1} related={related} lead={i === 0} level={activeLevel} />)}
    </div>
  );
}
