// AstaNews · 情报邸报 — 纯客户端，从 ./data/ 加载每日产物渲染。无构建步骤。
const LAYER = {
  model: ["🧠", "模型"], "post-training": ["🎛️", "后训练"], eval: ["📊", "评测"],
  data: ["🗂️", "数据"], infra: ["🏗️", "基建"], serving: ["⚡", "推理"], maas: ["☁️", "MaaS"],
  agent: ["🤖", "智能体"], embodied: ["🦾", "具身"], safety: ["🛡️", "安全"],
  product: ["📦", "产品"], business: ["💰", "商业"], devtool: ["🔧", "工具"],
};
const lz = (l) => (Array.isArray(l) ? l[0] : l) || "";
const dept = (l) => { const k = lz(l); const v = LAYER[k]; return v ? `${v[0]} ${v[1]}` : k; };
const esc = (s) => (s == null ? "" : String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])));

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

function renderIssues(eds, active) {
  const nav = document.getElementById("issues");
  if (!eds.length) { nav.innerHTML = '<div class="empty">暂无</div>'; return; }
  nav.innerHTML = eds.map((e, i) => `
    <a class="iss${e.date === active ? " active" : ""}" href="#${e.date}" data-date="${e.date}">
      <div class="d">${esc(e.date)}</div>
      <div class="m">No.${String(eds.length - i).padStart(3, "0")} · ${e.selected} 条 · ${(e.layers || []).length} 层</div>
    </a>`).join("");
}

function story(it, i) {
  const links = [];
  if (it.links?.primary) links.push(`<a href="${esc(it.links.primary)}" target="_blank" rel="noopener">一手源</a>`);
  if (it.links?.discussion) links.push(`<a href="${esc(it.links.discussion)}" target="_blank" rel="noopener">讨论</a>`);
  const [emoji] = LAYER[lz(it.layer)] || ["", ""];
  return `<article class="story" style="--i:${i}">
    <div class="num">${it.rank ?? i + 1}</div>
    <div class="dept"><span class="emoji">${emoji}</span>${esc(dept(it.layer))}</div>
    <h2>${esc(it.title)}</h2>
    <div class="body">${esc(it.readable)}</div>
    ${links.length ? `<div class="links">${links.join("")}</div>` : ""}
  </article>`;
}

let _ledgerAll = [];

function ledgerRender(items) {
  const selUrls = new Set();
  const by = {};
  for (const c of items) (by[c.source] = by[c.source] || []).push(c);
  return Object.keys(by).sort().map((src) => {
    const rows = by[src].map((c) => {
      const sel = c.selected;
      const sum = c.summary ? `<div class="lsum">${esc(c.summary)}</div>` : "";
      return `<li class="${sel ? "sel" : ""}">
        <div class="lhead"><span class="lb">${esc(dept(c.layer))}</span>
        <a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.title)}</a></div>${sum}</li>`;
    }).join("");
    return `<div class="lgroup"><h4>${esc(src)}<span class="cnt">${by[src].length}</span></h4><ul>${rows}</ul></div>`;
  }).join("");
}

function ledgerFilter(layer) {
  const items = layer ? _ledgerAll.filter((c) => c.layer === layer) : _ledgerAll;
  const el = document.getElementById("ledger-items");
  if (el) {
    el.innerHTML = ledgerRender(items);
    document.getElementById("ledger-count").textContent = `${items.length} 条`;
  }
  document.querySelectorAll(".lf-chip").forEach((c) => c.classList.toggle("active", c.dataset.layer === (layer || "")));
}

function ledger(d) {
  const all = d.all_candidates || [];
  if (!all.length) return "";
  _ledgerAll = all;
  const layers = {};
  for (const c of all) { const l = c.layer; if (l) layers[l] = (layers[l] || 0) + 1; }
  const chips = Object.entries(layers)
    .sort((a, b) => b[1] - a[1])
    .map(([l, n]) => { const v = LAYER[l]; const label = v ? `${v[0]} ${v[1]}` : l; return `<button class="lf-chip" data-layer="${esc(l)}">${label} ${n}</button>`; })
    .join("");
  return `<details class="ledger">
    <summary><span>全部信息 · <span id="ledger-count">${all.length} 条</span>候选（含未精选）</span><span class="chev">▸</span></summary>
    <div class="lf-bar"><button class="lf-chip active" data-layer="">全部 ${all.length}</button>${chips}</div>
    <div class="lcol" id="ledger-items">${ledgerRender(all)}</div>
  </details>`;
}

function renderIssue(d) {
  const el = document.getElementById("issue");
  const st = d.stats || {};
  const layers = (st.layers_covered || []).map((l) => dept(l)).join(" · ");
  const stories = (d.selected || []).map(story).join("");
  const radar = (d.radar || []).map((r) =>
    `<li><span class="tag">${esc(dept(r.layer))}</span>${esc(r.title)}${r.note ? "，" + esc(r.note) : ""}${r.link ? ` <a href="${esc(r.link)}" target="_blank" rel="noopener">↗</a>` : ""}</li>`).join("");
  const gaps = (d.gaps || []).map((g) => `<li>${esc(g)}</li>`).join("");
  el.innerHTML = `
    <div class="dateline">今日日报 · ${(st.layers_covered || []).length} LAYERS</div>
    <h1 class="ed-headline">${esc(d.date)}<span class="wd">${d.weekday ? " · " + esc(d.weekday) : ""}</span></h1>
    ${d.overview ? `<p class="ed-abstract">${esc(d.overview)}</p>` : ""}
    <div class="statbar">
      <span><b>${(d.selected || []).length}</b> 条精选</span><span class="sep">/</span>
      <span>覆盖 <b>${layers || "—"}</b></span><span class="sep">/</span>
      <span>候选 <b>${st.candidates ?? "—"}</b> 条</span>
      ${st.sources_ok != null ? `<span class="sep">/</span><span>源 <b>${st.sources_ok}</b> 成功${st.sources_failed ? ` · ${st.sources_failed} 失败` : ""}</span>` : ""}
    </div>
    ${stories ? `<div class="sec">本期要闻</div>${stories}` : ""}
    ${radar ? `<div class="sec">雷达 · 快报</div><ul class="briefs">${radar}</ul>` : ""}
    ${gaps ? `<div class="sec">数据缺口</div><div class="note"><h3>编者按 · 今日未覆盖</h3><ul>${gaps}</ul></div>` : ""}
    ${ledger(d)}`;
  window.scrollTo({ top: 0 });
}

let EDS = [];
async function show(date) {
  renderIssues(EDS, date);
  const idx = EDS.findIndex((e) => e.date === date);
  const issueNo = idx >= 0 ? EDS.length - idx : EDS.length;
  document.getElementById("tele-issue").textContent = `第 ${String(issueNo).padStart(3, "0")} 期`;
  const el = document.getElementById("issue");
  el.innerHTML = '<div class="loading">加载中…</div>';
  try { renderIssue(await getJSON(`data/${date}.json`)); }
  catch (e) { el.innerHTML = `<div class="empty">无法加载 ${esc(date)}（${esc(e.message)}）</div>`; }
}

async function boot() {
  let idx;
  try { idx = await getJSON("data/index.json"); EDS = idx.editions || []; }
  catch {
    document.getElementById("issues").innerHTML = '<div class="empty">暂无</div>';
    document.getElementById("issue").innerHTML = '<div class="empty">还没有发布任何 digest。跑一次 <code>/asta-news:daily-digest</code> 后发布即可。</div>';
    return;
  }
  if (!EDS.length) { document.getElementById("issue").innerHTML = '<div class="empty">暂无归档</div>'; renderIssues([], null); return; }
  const want = location.hash.slice(1);
  show(EDS.some((e) => e.date === want) ? want : EDS[0].date);
}
window.addEventListener("hashchange", () => { const d = location.hash.slice(1); if (d) show(d); });
document.addEventListener("click", (e) => {
  const a = e.target.closest(".iss"); if (a) { e.preventDefault(); location.hash = a.dataset.date; }
  const chip = e.target.closest(".lf-chip"); if (chip) { ledgerFilter(chip.dataset.layer || ""); }
});
boot();
