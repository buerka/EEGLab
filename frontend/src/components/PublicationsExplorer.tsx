import { useEffect, useMemo, useState } from 'react';
import {
  fetchPublications,
  formatUpdatedAt,
  type Publication,
  type PublicationsResponse,
  type Researcher,
} from '../lib/publications';

type ActiveFilter = '代表作' | '全部' | string;

export default function PublicationsExplorer() {
  const [data, setData] = useState<PublicationsResponse | null>(null);
  const [error, setError] = useState('');
  const [activeResearcher, setActiveResearcher] = useState('all');
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>('代表作');
  const [query, setQuery] = useState('');

  const load = (refresh = false) => {
    setError('');
    fetchPublications(undefined, { refresh })
      .then(setData)
      .catch(reason => setError(reason instanceof Error ? reason.message : '论文服务暂时不可用'));
  };

  useEffect(() => { load(); }, []);

  const visible = useMemo(() => {
    if (!data) return [];
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return data.papers.filter(paper => {
      const researcherMatch = activeResearcher === 'all'
        || paper.researchers.some(researcher => researcher.slug === activeResearcher);
      const filterMatch = activeFilter === '全部'
        || (activeFilter === '代表作' ? paper.representative : paper.tags.includes(activeFilter));
      const queryMatch = !normalizedQuery
        || `${paper.title} ${paper.authors} ${paper.journal}`.toLocaleLowerCase().includes(normalizedQuery);
      return researcherMatch && filterMatch && queryMatch;
    });
  }, [data, activeResearcher, activeFilter, query]);

  const selectedResearcher = data?.researchers.find(item => item.slug === activeResearcher);
  const years = [...new Set(visible.map(paper => paper.year))].sort((a, b) => b - a);

  if (error) {
    return (
      <div className="publication-error" role="alert">
        <strong>暂时无法连接论文服务</strong>
        <p>{error}</p>
        <button onClick={() => load(true)}>重新加载</button>
        <style>{errorStyles}</style>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="publication-loading" aria-label="正在加载论文">
        <span /><span /><span />
        <style>{loadingStyles}</style>
      </div>
    );
  }

  return (
    <div className="publications-explorer">
      <div className="researcher-switcher" aria-label="按研究者筛选">
        <button
          className={activeResearcher === 'all' ? 'active' : ''}
          onClick={() => setActiveResearcher('all')}
        >
          <span className="researcher-avatar all">ALL</span>
          <span><strong>全部成员</strong><small>{data.total} 篇</small></span>
        </button>
        {data.researchers.map(researcher => (
          <button
            key={researcher.slug}
            className={activeResearcher === researcher.slug ? 'active' : ''}
            onClick={() => setActiveResearcher(researcher.slug)}
          >
            {researcher.avatarUrl
              ? <img className="researcher-avatar" src={researcher.avatarUrl} alt="" />
              : <span className="researcher-avatar">{researcher.name.slice(0, 1)}</span>}
            <span><strong>{researcher.name}</strong><small>{researcher.paperCount} 篇</small></span>
          </button>
        ))}
      </div>

      <div className="publication-toolbar">
        <div className="filter-bar">
          {['代表作', ...data.filterTags, '全部'].map(filter => (
            <button
              key={filter}
              className={activeFilter === filter ? 'active' : ''}
              onClick={() => setActiveFilter(filter)}
            >{filter}</button>
          ))}
        </div>
        <label className="paper-search">
          <span className="sr-only">搜索论文</span>
          <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="4.5" /><path d="m10.5 10.5 3 3" /></svg>
          <input value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索标题、作者或期刊" />
        </label>
      </div>

      <div className="publication-meta">
        <span>显示 {visible.length} / {data.total} 篇</span>
        <span>更新于 {formatUpdatedAt(data.updatedAt)}</span>
        {selectedResearcher?.googleScholarUrl && (
          <a href={selectedResearcher.googleScholarUrl} target="_blank" rel="noopener noreferrer">
            {selectedResearcher.name}的 Google Scholar ↗
          </a>
        )}
        {selectedResearcher?.scholarMetrics?.totalCitations != null && (
          <span>
            Scholar 总引用 {selectedResearcher.scholarMetrics.totalCitations}
            {selectedResearcher.scholarMetrics.hIndex != null
              ? ` · h-index ${selectedResearcher.scholarMetrics.hIndex}` : ''}
          </span>
        )}
      </div>

      <div className="paper-list">
        {years.map(year => (
          <section key={year} className="paper-year-group">
            <div className="year-divider"><span>{year}</span></div>
            {visible.filter(paper => paper.year === year).map(paper => (
              <PaperRow paper={paper} key={paper.id} />
            ))}
          </section>
        ))}
        {!visible.length && <p className="no-results">当前条件下暂无论文</p>}
      </div>
      <style>{explorerStyles}</style>
    </div>
  );
}

function PaperRow({ paper }: { paper: Publication }) {
  return (
    <article className="paper-row">
      <div className="pr-num">{paper.num}</div>
      <div className="pr-body">
        {paper.doi
          ? <a className="pr-title" href={`https://doi.org/${paper.doi}`} target="_blank" rel="noopener noreferrer">{paper.title}</a>
          : <div className="pr-title">{paper.title}</div>}
        <div className="pr-authors">{paper.authors}</div>
        <div className="paper-researchers">
          {paper.researchers.map(researcher => (
            <span key={researcher.slug} title={researcher.isCorresponding ? '通讯作者' : undefined}>
              {researcher.name}{researcher.isCorresponding ? ' *' : ''}
            </span>
          ))}
        </div>
        <div className="pr-tags">
          {paper.journal && <span className="pr-tag venue">{paper.journal}</span>}
          {paper.impactFactor && <span className={`pr-tag if ${paper.impactFactor >= 7 ? 'gold' : paper.impactFactor >= 5 ? 'blue' : ''}`}>IF {paper.impactFactor}</span>}
          {paper.quartile && <span className={`pr-tag rank ${paper.isTop ? 'top' : ''}`}>{paper.quartile}{paper.isTop ? ' Top' : ''}</span>}
          {paper.tags.filter(tag => !['一区', '二区', '会议', '其他'].includes(tag)).map(tag => (
            <span className="pr-tag topic" key={tag}>{tag}</span>
          ))}
          <span className={`pr-tag source ${paper.sourceStatus === 'confirmed' ? 'confirmed' : ''}`}>
            {paper.sourceStatus === 'confirmed'
              ? 'OpenAlex + Scholar 已核验'
              : paper.sourceStatus === 'scholar_only' ? 'Scholar 已确认' : 'OpenAlex'}
          </span>
          {paper.citationSources?.googleScholar != null && (
            <span className="pr-tag citation">Scholar 引用 {paper.citationSources.googleScholar}</span>
          )}
          {paper.citationSources?.openalex != null && (
            <span className="pr-tag citation">OpenAlex 引用 {paper.citationSources.openalex}</span>
          )}
        </div>
      </div>
      <div className="pr-year">{paper.year}</div>
    </article>
  );
}

const loadingStyles = `
  .publication-loading{display:grid;gap:12px}.publication-loading span{height:94px;border-radius:10px;background:linear-gradient(90deg,#f1f1f1,#fafafa,#f1f1f1);background-size:200% 100%;animation:publication-loading 1.5s infinite}@keyframes publication-loading{to{background-position:-200% 0}}
`;

const errorStyles = `
  .publication-error{padding:36px;border:1px solid rgba(180,30,30,.14);border-radius:12px;background:rgba(180,30,30,.035);color:#444}.publication-error strong{color:#a02727}.publication-error p{font-size:13px;color:#888}.publication-error button{padding:8px 16px;border:1px solid rgba(0,0,0,.15);border-radius:999px;background:#fff;cursor:pointer}
`;

const explorerStyles = `
  .publications-explorer{min-width:0}.researcher-switcher{display:flex;gap:10px;overflow-x:auto;padding:2px 0 22px;margin-bottom:24px;border-bottom:1px solid rgba(0,0,0,.08)}
  .researcher-switcher button{display:flex;align-items:center;gap:10px;flex:0 0 auto;padding:9px 13px;border:1px solid rgba(0,0,0,.09);border-radius:12px;background:#fff;color:#444;cursor:pointer;text-align:left;transition:.18s}
  .researcher-switcher button:hover,.researcher-switcher button.active{border-color:rgba(0,87,255,.35);background:rgba(0,87,255,.04);color:#0057FF}.researcher-switcher button>span:last-child{display:grid;gap:1px}.researcher-switcher strong{font-size:12px}.researcher-switcher small{font-size:10px;color:#999}
  .researcher-avatar{width:32px;height:32px;border-radius:50%;object-fit:cover;background:#f1f1f1;display:grid;place-items:center;font-size:11px;font-weight:700;color:#666}.researcher-avatar.all{font-family:'SF Mono',monospace;font-size:9px}
  .publication-toolbar{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:18px}.filter-bar{display:flex;flex-wrap:wrap;gap:6px}.filter-bar button{padding:6px 14px;font-size:11px;font-weight:500;border-radius:999px;border:1px solid rgba(0,0,0,.1);background:transparent;color:#888;cursor:pointer}.filter-bar button:hover,.filter-bar button.active{background:rgba(0,87,255,.07);border-color:rgba(0,87,255,.25);color:#0057FF}
  .paper-search{display:flex;align-items:center;gap:7px;min-width:220px;padding:8px 11px;border:1px solid rgba(0,0,0,.1);border-radius:9px;background:#fff}.paper-search svg{width:14px;height:14px;fill:none;stroke:#999;stroke-width:1.3}.paper-search input{width:100%;border:0;outline:0;font:12px inherit;color:#333}.paper-search input::placeholder{color:#aaa}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
  .publication-meta{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:28px;color:#999;font:10px 'SF Mono',monospace}.publication-meta a{margin-left:auto;color:#0057FF}.paper-list{display:flex;flex-direction:column}.year-divider{display:flex;align-items:center;gap:16px;padding:24px 16px 10px;font-size:11px;letter-spacing:3px;color:#aaa;font-family:'SF Mono',monospace}.year-divider:after{content:'';flex:1;height:1px;background:rgba(0,0,0,.08)}
  .paper-row{display:grid;grid-template-columns:44px 1fr auto;gap:20px;align-items:start;padding:20px 16px;border-radius:8px;transition:background .15s}.paper-row:hover{background:#f7f7f7}.pr-num{font:11px 'SF Mono',monospace;color:#bbb;padding-top:3px}.pr-title{display:block;font-size:15px;font-weight:550;line-height:1.55;margin-bottom:6px;color:#0a0a0a}.pr-title:hover{color:#0057FF}.pr-authors{font-size:12px;color:#888;line-height:1.6}.paper-researchers{display:flex;gap:5px;flex-wrap:wrap;margin:7px 0 9px}.paper-researchers span{font-size:10px;padding:2px 7px;border-radius:999px;background:rgba(0,87,255,.06);color:#0057FF}.pr-tags{display:flex;flex-wrap:wrap;gap:5px}.pr-tag{font:10px 'SF Mono',monospace;padding:2px 7px;border-radius:4px}.pr-tag.venue{background:rgba(0,87,255,.06);color:#0057FF;border:1px solid rgba(0,87,255,.12)}.pr-tag.if,.pr-tag.rank{background:#f0f0f0;color:#777}.pr-tag.if.gold{background:rgba(196,143,25,.09);color:#a57408}.pr-tag.if.blue{background:rgba(0,87,255,.07);color:#0057FF}.pr-tag.rank.top{background:rgba(40,180,100,.08);color:#1a9a56}.pr-tag.topic{color:#999;border:1px solid rgba(0,0,0,.08)}.pr-year{font:11px 'SF Mono',monospace;color:#5b8dee;padding-top:3px}.no-results{text-align:center;color:#aaa;font-size:13px;padding:50px 16px}
  .pr-tag.source{color:#777;background:#f3f3f3}.pr-tag.source.confirmed{color:#157a45;background:rgba(40,180,100,.08)}.pr-tag.citation{color:#756233;background:rgba(196,143,25,.08)}
  @media(max-width:760px){.publication-toolbar{display:grid}.paper-search{min-width:0}.publication-meta a{margin-left:0}.paper-row{grid-template-columns:1fr;gap:8px}.pr-num,.pr-year{display:none}}
`;
