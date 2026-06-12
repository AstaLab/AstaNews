// AstaNews 静态站点：纯客户端，从 ./data/ 加载每日产物渲染。无构建步骤。
const LAYER = {
  model: "🧠 model", "post-training": "🎛️ post-training", eval: "📊 eval",
  data: "🗂️ data", infra: "🏗️ infra", serving: "⚡ serving", maas: "☁️ maas",
  agent: "🤖 agent", embodied: "🦾 embodied", safety: "🛡️ safety",
  product: "📦 product", business: "💰 business", devtool: "🔧 devtool",
};
const layerLabel = (l) => LAYER[l] || l;
const esc = (s) => (s == null ? "" : String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])));

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

function renderNav(editions, active) {
  const nav = document.getElementById("edition-nav");
  if (!editions.length) { nav.innerHTML = '<div class="empty">暂无归档</div>'; return; }
  nav.innerHTML = editions.map((e) => `
    <a class="nav-item${e.date === active ? " active" : ""}" href="#${e.date}" data-date="${e.date}">
      <div class="nav-date">${esc(e.date)}</div>
      <div class="nav-sub">${e.selected} 条 · ${(e.layers || []).length} 层</div>
    </a>`).join("");
}

function card(it) {
  const links = [];
  if (it.links?.primary) links.push(`<a href="${esc(it.links.primary)}" target="_blank" rel="noopener">一手源</a>`);
  if (it.links?.discussion) links.push(`<a href="${esc(it.links.discussion)}" target="_blank" rel="noopener">讨论</a>`);
  const facts = (it.facts || []).map((f) => `<li>${esc(f)}</li>`).join("");
  return `<div class="card">
    <div class="card-top">
      <span class="rank">${it.rank ?? ""}</span>
      <span class="badge">${esc(layerLabel(it.layer))}</span>
    </div>
    <h3>${esc(it.title)}</h3>
    <div class="readable">${esc(it.readable)}</div>
    ${facts ? `<ul class="facts">${facts}</ul>` : ""}
    ${links.length ? `<div class="card-links">${links.join("")}</div>` : ""}
  </div>`;
}

function allCandidates(d) {
  const all = d.all_candidates || [];
  if (!all.length) return "";
  const selUrls = new Set((d.selected || []).concat(d.radar || []).map((x) => x.links?.primary || x.link).filter(Boolean));
  const bySource = {};
  for (const c of all) (bySource[c.source] = bySource[c.source] || []).push(c);
  const groups = Object.keys(bySource).sort().map((src) => {
    const items = bySource[src].map((c) => {
      const sel = c.selected || selUrls.has(c.url);
      return `<li class="${sel ? "is-selected" : ""}">
        <span class="mini-badge">${esc(layerLabel(c.layer ? (Array.isArray(c.layer) ? c.layer[0] : c.layer) : ""))}</span>
        <a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.title)}</a></li>`;
    }).join("");
    return `<div class="src-group"><h4>${esc(src)} · ${bySource[src].length}</h4><ul>${items}</ul></div>`;
  }).join("");
  return `<details class="all">
    <summary><span>全部信息 · ${all.length} 条候选（含未精选）</span><span class="chev">▸</span></summary>
    <div class="all-body">
      <p class="all-note">这是当天抓到的全部候选，★ 为精选条目。精选只是为微信群做的减法；要全景看这里。</p>
      ${groups}
    </div>
  </details>`;
}

function renderEdition(d) {
  const el = document.getElementById("edition");
  const stats = d.stats || {};
  const selected = (d.selected || []).map(card).join("");
  const radar = (d.radar || []).map((r) => `<li><span class="badge">${esc(layerLabel(r.layer))}</span>${esc(r.title)}${r.note ? " — " + esc(r.note) : ""}${r.link ? ` <a href="${esc(r.link)}" target="_blank" rel="noopener">↗</a>` : ""}</li>`).join("");
  const gaps = (d.gaps || []).map((g) => `<li>${esc(g)}</li>`).join("");
  el.innerHTML = `
    <div class="ed-head">
      <div class="ed-date">${esc(d.date)}${d.weekday ? " · " + esc(d.weekday) : ""}</div>
      <h1 class="ed-title">${esc(d.headline || "AI 全栈每日情报")}</h1>
      ${d.overview ? `<p class="ed-overview">${esc(d.overview)}</p>` : ""}
      <div class="ed-stats">
        <span><b>${(d.selected || []).length}</b> 条精选</span>
        <span>覆盖 <b>${(stats.layers_covered || []).map(layerLabel).join("、") || "—"}</b></span>
        <span>候选 <b>${stats.candidates ?? "—"}</b> 条</span>
        ${stats.sources_ok != null ? `<span>源 <b>${stats.sources_ok}</b> 成功${stats.sources_failed ? ` / ${stats.sources_failed} 失败` : ""}</span>` : ""}
      </div>
    </div>
    ${selected ? `<div class="section-label">精选</div>${selected}` : ""}
    ${radar ? `<div class="section-label">📡 雷达</div><ul class="radar-list">${radar}</ul>` : ""}
    ${gaps ? `<div class="section-label">⚠️ 数据缺口</div><div class="gap-box"><ul class="gap-list">${gaps}</ul></div>` : ""}
    ${allCandidates(d)}
  `;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

let EDITIONS = [];
async function show(date) {
  renderNav(EDITIONS, date);
  const el = document.getElementById("edition");
  el.innerHTML = '<div class="loading">加载中…</div>';
  try {
    renderEdition(await getJSON(`data/${date}.json`));
  } catch (e) {
    el.innerHTML = `<div class="empty">无法加载 ${esc(date)}：${esc(e.message)}</div>`;
  }
}

async function boot() {
  try {
    const idx = await getJSON("data/index.json");
    EDITIONS = idx.editions || [];
  } catch (e) {
    document.getElementById("edition-nav").innerHTML = '<div class="empty">暂无数据</div>';
    document.getElementById("edition").innerHTML = `<div class="empty">还没有发布任何 digest。跑一次 <code>/asta-news:daily-digest</code> 后用 <code>publish_site.py</code> 发布。</div>`;
    return;
  }
  if (!EDITIONS.length) { document.getElementById("edition").innerHTML = '<div class="empty">暂无归档</div>'; renderNav([], null); return; }
  const want = location.hash.slice(1);
  show(EDITIONS.some((e) => e.date === want) ? want : EDITIONS[0].date);
}
window.addEventListener("hashchange", () => { const d = location.hash.slice(1); if (d) show(d); });
document.addEventListener("click", (e) => { const a = e.target.closest(".nav-item"); if (a) { e.preventDefault(); location.hash = a.dataset.date; } });
boot();
