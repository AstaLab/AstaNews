"use client";
import { useEffect, useState } from "react";
import { API, layerName } from "../../lib/config";

// 网站即控制台。本地/全功能模式（配 NEXT_PUBLIC_API 指向 services 后端）下可用：
// 看状态/源/配置、服务端语义检索、触发抓取。静态公开站无后端 → 引导。
function Card({ title, children }) {
  return (
    <div style={{ border: "1px solid var(--rule)", borderRadius: 12, padding: "18px 20px", marginBottom: 16, background: "var(--card)" }}>
      <div style={{ fontFamily: "var(--mono)", fontSize: 12, letterSpacing: ".1em", textTransform: "uppercase", color: "var(--seal-2)", marginBottom: 12 }}>{title}</div>
      {children}
    </div>
  );
}

export default function Console() {
  const [health, setHealth] = useState(null);
  const [sources, setSources] = useState(null);
  const [config, setConfig] = useState(null);
  const [err, setErr] = useState(null);
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!API) return;
    (async () => {
      try {
        setHealth(await (await fetch(`${API}/api/health`)).json());
        setSources(await (await fetch(`${API}/api/sources`)).json());
        setConfig(await (await fetch(`${API}/api/config`)).json());
      } catch (e) { setErr(String(e)); }
    })();
  }, []);

  async function search(e) {
    e.preventDefault();
    if (!API || !q.trim()) return;
    try {
      const d = await (await fetch(`${API}/api/search?q=${encodeURIComponent(q)}&top=10`)).json();
      setRes(d.results || []);
    } catch (e) { setMsg(`检索失败：${e}`); }
  }
  async function trigger() {
    if (!API) return;
    setMsg("触发中…");
    try { const d = await (await fetch(`${API}/api/run/fetch`, { method: "POST" })).json(); setMsg(`已触发抓取 (pid ${d.pid})`); }
    catch (e) { setMsg(`触发失败：${e}`); }
  }

  if (!API) {
    return (
      <>
        <div className="dateline">控制台 · 本地/全功能模式</div>
        <p className="deck">网站即一切入口——查看 / 检索 / 触发 / 配置。公开站为静态只读；要解锁控制台，本地起后端再连：</p>
        <Card title="启用">
          <pre style={{ fontFamily: "var(--mono)", fontSize: 13, whiteSpace: "pre-wrap", margin: 0, color: "var(--ink-2)" }}>{`# 1. 起 services 后端（零安装）
uv run services/app.py            # http://127.0.0.1:8799

# 2. 连着后端跑前端
cd web && NEXT_PUBLIC_API=http://127.0.0.1:8799 npm run dev
# 然后这页就能看源/配置、做服务端语义检索、触发抓取`}</pre>
        </Card>
        <Card title="架构">
          <div style={{ fontSize: 14, color: "var(--ink-2)", lineHeight: 1.7 }}>
            公开 GitHub Pages：静态只读（前端直读数据 + 浏览器内检索）。<br />
            本地连后端：服务端语义检索 + 读写配置 + 触发运行。账号体系预留（services 的 require_auth 钩子）。
          </div>
        </Card>
      </>
    );
  }

  return (
    <>
      <div className="dateline">控制台 · 已连后端 {API}</div>
      {err && <Card title="错误"><span style={{ color: "var(--seal)" }}>{err}（确认 services 后端在跑）</span></Card>}
      <Card title="状态">
        {health ? <span style={{ fontFamily: "var(--mono)", fontSize: 13 }}>ok · {health.editions} 期 · {health.data_dir}</span> : "…"}
      </Card>
      <Card title="服务端语义检索">
        <form onSubmit={search} style={{ display: "flex", gap: 10 }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="语义查询…" style={{ flex: 1, padding: "8px 12px", border: "1px solid var(--rule-2)", borderRadius: 7, background: "var(--paper)", color: "var(--ink)" }} />
          <button className="chip on" style={{ background: "var(--seal)", color: "#f4efe6", border: "none" }}>搜</button>
        </form>
        <ul className="rows" style={{ marginTop: 12 }}>
          {res.map((r, i) => (
            <li className="row" key={r.id || i}><div className="rhead">
              <span className="lb">{r.date} · {layerName(r.layer)} · {r.score?.toFixed(2)}</span>
              <a href={r.url} target="_blank" rel="noopener">{r.title}</a></div></li>
          ))}
        </ul>
      </Card>
      <Card title="数据源">
        {sources ? <span style={{ fontFamily: "var(--mono)", fontSize: 13 }}>{sources.count} 源 · {sources.enabled} 启用</span> : "…"}
      </Card>
      <Card title="配置">
        {config ? <span style={{ fontFamily: "var(--mono)", fontSize: 12 }}>{Object.keys(config).join(" · ")}</span> : "…"}
      </Card>
      <Card title="触发">
        <button onClick={trigger} className="chip" style={{ borderColor: "var(--seal)" }}>触发抓取</button>
        <span style={{ marginLeft: 12, fontSize: 13, color: "var(--muted)" }}>{msg}</span>
        <div style={{ fontSize: 12, color: "var(--faint)", marginTop: 8 }}>完整 digest（评分/改写）由 5am cron 与 GitHub Actions 跑。</div>
      </Card>
    </>
  );
}
