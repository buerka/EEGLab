import { useEffect, useState } from 'react';
import { fetchPublications, type Publication } from '../lib/publications';

export default function FeaturedPublications() {
  const [papers, setPapers] = useState<Publication[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams({ representative: 'true', limit: '20' });
    fetchPublications(params).then(data => {
      setPapers([...data.papers]
        .sort((a, b) => (b.impactFactor ?? 0) - (a.impactFactor ?? 0) || b.year - a.year)
        .slice(0, 3));
    }).catch(() => setError(true));
  }, []);

  if (error) {
    return <p className="featured-status">论文服务暂时不可用，请前往科研成果页稍后重试。</p>;
  }
  if (!papers.length) {
    return <div className="featured-loading" aria-label="正在加载代表论文"><span /><span /><span /></div>;
  }
  return (
    <div className="featured-publications">
      {papers.map(paper => (
        <a href="/achievements" className="featured-paper" key={paper.id}>
          <span className="featured-year">{paper.year}</span>
          <div className="featured-body">
            <p className="featured-title">{paper.title}</p>
            <p className="featured-journal">
              {paper.journal}{paper.impactFactor ? ` · IF ${paper.impactFactor}` : ''}
            </p>
            <div className="featured-researchers">
              {paper.researchers.map(researcher => <span key={researcher.slug}>{researcher.name}</span>)}
            </div>
          </div>
          <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M3 10h14M12 5l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </a>
      ))}
      <style>{`
        .featured-publications { display:flex; flex-direction:column; }
        .featured-paper { display:grid; grid-template-columns:72px 1fr 28px; gap:24px; align-items:center; padding:22px 18px; border-bottom:1px solid rgba(0,0,0,.08); color:inherit; transition:background .2s; }
        .featured-paper:hover { background:#f7f7f7; }
        .featured-year { font:12px 'SF Mono',monospace; color:#0057FF; }
        .featured-title { margin:0 0 7px; font-size:16px; line-height:1.5; font-weight:600; }
        .featured-journal { margin:0; font-size:12px; color:#888; }
        .featured-researchers { display:flex; gap:5px; margin-top:8px; }
        .featured-researchers span { font-size:10px; color:#0057FF; background:rgba(0,87,255,.06); padding:2px 7px; border-radius:999px; }
        .featured-paper svg { width:20px; color:#888; }
        .featured-status { color:#888; font-size:14px; padding:24px 18px; }
        .featured-loading { display:grid; gap:12px; }
        .featured-loading span { height:72px; border-radius:8px; background:linear-gradient(90deg,#f2f2f2,#fafafa,#f2f2f2); background-size:200% 100%; animation:paper-loading 1.5s infinite; }
        @keyframes paper-loading { to { background-position:-200% 0; } }
        @media(max-width:560px){.featured-paper{grid-template-columns:1fr 20px}.featured-year{display:none}}
      `}</style>
    </div>
  );
}
