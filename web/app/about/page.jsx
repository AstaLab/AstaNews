import { SITE } from "../../lib/config";

export const metadata = { title: "关于 · AstaNews" };

export default function About() {
  return (
    <div style={{ maxWidth: 720 }}>
      <div className="dateline">关于 AstaNews</div>
      <p className="deck">一份面向 AI 从业者的每日情报。我们每天通览 AI 全栈——前沿论文、模型发布、评测、推理与基建、智能体、具身、安全、产品与商业动向——挑出当天真正重要的进展，配上中文导读。</p>
      <div className="story" style={{ gridTemplateColumns: "1fr" }}>
        <div className="body">
{`每日两个粒度：日报通览当天全栈精选；精选只留最重要的几条。

多视角：同一批新闻可按你关心的角度重排——全栈 / 技术 / 产品 / 商业 / 研究 / 具身。

按领域分类浏览，相关报道互相串联，全站可搜索。

数据源开放贡献，欢迎在 GitHub 提交你认为值得追踪的来源。`}
        </div>
        <div className="links" style={{ gridColumn: 1 }}>
          <a href={`https://github.com/${SITE.repo}`} target="_blank" rel="noopener">GitHub 仓库</a>
        </div>
      </div>
    </div>
  );
}
