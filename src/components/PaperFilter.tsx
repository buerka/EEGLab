import { useState } from 'react';

export interface Paper {
  num: string;
  year: number;
  title: string;
  authors: string;
  journal: string;
  quartile?: string;
  impactFactor?: number;
  isTop?: boolean;
  tags: string[];
  type: 'journal' | 'conference';
}

interface Props {
  papers: Paper[];
  filterTags: string[];
}

function highlightAuthor(authors: string) {
  return authors.replace(/(Y\. Yan)/g, '<mark>$1</mark>');
}

export default function PaperFilter({ papers, filterTags }: Props) {
  const [active, setActive] = useState('全部');

  const visible = active === '全部'
    ? papers
    : papers.filter(p => p.tags.includes(active));

  const years = [...new Set(visible.map(p => p.year))].sort((a, b) => b - a);

  return (
    <div>
      <div className="filter-bar">
        {filterTags.map(tag => (
          <button
            key={tag}
            className={`filter-chip ${active === tag ? 'active' : ''}`}
            onClick={() => setActive(tag)}
          >
            {tag}
          </button>
        ))}
      </div>

      <div className="paper-list">
        {years.map(year => (
          <div key={year}>
            <div className="year-divider">
              <span>{year}</span>
            </div>
            {visible.filter(p => p.year === year).map(paper => (
              <div key={paper.num} className="paper-row">
                <div className="pr-num">{paper.num}</div>
                <div className="pr-body">
                  <div className="pr-title">{paper.title}</div>
                  <div
                    className="pr-authors"
                    dangerouslySetInnerHTML={{ __html: highlightAuthor(paper.authors) }}
                  />
                  <div className="pr-tags">
                    <span className="pr-tag venue">{paper.journal}</span>
                    {paper.impactFactor && (
                      <span className="pr-tag if">IF {paper.impactFactor}</span>
                    )}
                    {paper.quartile && (
                      <span className={`pr-tag rank ${paper.isTop ? 'top' : ''}`}>
                        {paper.quartile}{paper.isTop ? ' Top' : ''}
                      </span>
                    )}
                    {paper.tags
                      .filter(t => !['一区', '二区', '会议'].includes(t))
                      .map(t => (
                        <span key={t} className="pr-tag topic">{t}</span>
                      ))}
                  </div>
                </div>
                <div className="pr-year">{paper.year}</div>
              </div>
            ))}
          </div>
        ))}
        {visible.length === 0 && (
          <p className="no-results">该分类下暂无论文</p>
        )}
      </div>

      <style>{`
        .filter-bar {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-bottom: 48px;
        }
        .filter-chip {
          padding: 6px 16px;
          font-size: 12px;
          font-weight: 500;
          border-radius: 100px;
          border: 1.5px solid rgba(0,0,0,0.1);
          background: transparent;
          color: #888;
          cursor: pointer;
          transition: background 0.15s, color 0.15s, border-color 0.15s;
          font-family: inherit;
          letter-spacing: 0.2px;
          line-height: 1.5;
        }
        .filter-chip:hover {
          border-color: rgba(0,0,0,0.25);
          color: #333;
          background: #f5f5f5;
        }
        .filter-chip.active {
          background: rgba(0,87,255,0.07);
          border-color: rgba(0,87,255,0.25);
          color: #0057FF;
        }
        .paper-list {
          display: flex;
          flex-direction: column;
        }
        .year-divider {
          display: flex;
          align-items: center;
          gap: 16px;
          padding: 24px 16px 10px;
          font-size: 11px;
          letter-spacing: 3px;
          color: #aaa;
          font-family: 'SF Mono', monospace;
        }
        .year-divider::after {
          content: '';
          flex: 1;
          height: 1px;
          background: rgba(0,0,0,0.08);
        }
        .paper-row {
          display: grid;
          grid-template-columns: 44px 1fr auto;
          gap: 20px;
          align-items: start;
          padding: 20px 16px;
          border-radius: 8px;
          transition: background 0.15s;
        }
        .paper-row:hover {
          background: #f7f7f7;
        }
        .pr-num {
          font-size: 11px;
          color: #bbb;
          font-family: 'SF Mono', monospace;
          padding-top: 3px;
          font-variant-numeric: tabular-nums;
        }
        .pr-title {
          font-size: 15px;
          font-weight: 500;
          line-height: 1.55;
          margin-bottom: 6px;
          color: #0A0A0A;
          letter-spacing: -0.01em;
        }
        .pr-authors {
          font-size: 12px;
          color: #888;
          margin-bottom: 10px;
          line-height: 1.6;
        }
        .pr-authors mark {
          background: none;
          color: #0057FF;
          font-weight: 600;
        }
        .pr-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 5px;
        }
        .pr-tag {
          display: inline-block;
          font-size: 11px;
          padding: 2px 8px;
          border-radius: 4px;
          font-family: 'SF Mono', monospace;
        }
        .pr-tag.venue {
          background: rgba(0,87,255,0.06);
          color: #0057FF;
          border: 1px solid rgba(0,87,255,0.12);
        }
        .pr-tag.if {
          background: #f0f0f0;
          color: #888;
        }
        .pr-tag.rank {
          background: #f0f0f0;
          color: #888;
        }
        .pr-tag.rank.top {
          background: rgba(40,180,100,0.07);
          color: #1a9a56;
        }
        .pr-tag.topic {
          background: transparent;
          color: #aaa;
          border: 1px solid rgba(0,0,0,0.08);
        }
        .pr-year {
          font-size: 11px;
          color: #5B8DEE;
          font-family: 'SF Mono', monospace;
          padding-top: 3px;
          white-space: nowrap;
          font-variant-numeric: tabular-nums;
        }
        .no-results {
          color: #aaa;
          font-size: 14px;
          padding: 40px 16px;
          text-align: center;
        }
        @media (max-width: 560px) {
          .paper-row { grid-template-columns: 1fr; gap: 8px; }
          .pr-num, .pr-year { display: none; }
        }
      `}</style>
    </div>
  );
}
