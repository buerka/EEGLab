import { useEffect, useState } from 'react';
import { fetchPublications, type Publication } from '../lib/publications';

interface Props {
  tags: string[];
  limit?: number;
  variant?: 'overview' | 'detail';
}

function matches(paper: Publication, researchTags: string[]) {
  return paper.tags.some(tag => researchTags.some(researchTag => (
    tag.includes(researchTag.slice(0, 3)) || researchTag.includes(tag.slice(0, 3))
  )));
}

export default function RelatedPublications({ tags, limit = 3, variant = 'detail' }: Props) {
  const [papers, setPapers] = useState<Publication[] | null>(null);
  useEffect(() => {
    fetchPublications().then(data => setPapers(data.papers.filter(paper => matches(paper, tags)).slice(0, limit)))
      .catch(() => setPapers([]));
  }, [tags.join('|'), limit]);

  if (papers === null) return <div className="related-paper-loading">正在加载相关论文…</div>;
  if (!papers.length) return null;
  return (
    <section className={`related-publications ${variant}`}>
      <h2>{variant === 'detail' ? '相关论文' : '相关论文'}</h2>
      <div>
        {papers.map(paper => (
          <a href="/achievements" key={paper.id}>
            <span className="related-year">{paper.year}</span>
            <span className="related-title">{paper.title}</span>
            <span className="related-journal">{paper.journal}</span>
          </a>
        ))}
      </div>
      {variant === 'detail' && <a className="related-all" href="/achievements">查看全部成果 →</a>}
      <style>{`
        .related-publications { margin-top:42px; padding-top:30px; border-top:1px solid rgba(0,0,0,.08); }
        .related-publications h2 { margin:0 0 16px; font-size:12px; letter-spacing:.12em; color:#888; font-weight:600; }
        .related-publications a:not(.related-all) { display:grid; grid-template-columns:48px 1fr minmax(100px,220px); gap:14px; align-items:start; padding:13px 8px; border-radius:7px; color:inherit; }
        .related-publications a:not(.related-all):hover { background:#f7f7f7; }
        .related-year { color:#0057FF; font:11px 'SF Mono',monospace; }
        .related-title { font-size:13px; line-height:1.5; }
        .related-journal { color:#888; font-size:11px; text-align:right; }
        .related-all { display:inline-block; margin-top:16px; font-size:13px; color:#0057FF; }
        .related-paper-loading { margin-top:32px; color:#aaa; font-size:12px; }
        @media(max-width:640px){.related-publications a:not(.related-all){grid-template-columns:42px 1fr}.related-journal{display:none}}
      `}</style>
    </section>
  );
}
