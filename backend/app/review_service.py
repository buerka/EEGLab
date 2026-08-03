from __future__ import annotations

import json
import sqlite3

from .classification import classify
from .config import Settings
from .database import connect, normalize_doi, normalize_title, set_metadata, utc_now


def apply_scholar_review_rules(settings: Settings) -> dict:
    """把已审核候选物化为论文关联或永久排除，不访问任何外部 API。"""
    applied = accepted = excluded = 0
    now = utc_now()
    with connect(settings.database_path) as connection:
        rows = connection.execute(
            """
            SELECT sc.*, rr.decision, rr.target_openalex_id, rr.target_doi,
                   rr.target_normalized_title
            FROM scholar_candidates sc
            JOIN scholar_review_rules rr
              ON rr.researcher_id=sc.researcher_id AND rr.citation_id=sc.citation_id
            ORDER BY sc.id
            """
        ).fetchall()
        for row in rows:
            if row['decision'] == 'accept':
                accept_scholar_article(connection, row['researcher_id'], dict(row), row, now)
            if row['missing_since'] is None:
                if row['decision'] == 'accept':
                    accepted += 1
                else:
                    excluded += 1
                connection.execute(
                    'UPDATE scholar_candidates SET missing_since=? WHERE id=?',
                    (now, row['id']),
                )
                applied += 1
        if applied:
            set_metadata(connection, 'snapshot_version', now)
            set_metadata(connection, 'last_review_at', now)
    return {'applied': applied, 'accepted': accepted, 'excluded': excluded}


def load_review_rules(
    connection: sqlite3.Connection, researcher_id: int
) -> dict[str, sqlite3.Row]:
    rows = connection.execute(
        'SELECT * FROM scholar_review_rules WHERE researcher_id=?',
        (researcher_id,),
    ).fetchall()
    return {row['citation_id']: row for row in rows}


def accept_scholar_article(
    connection: sqlite3.Connection,
    researcher_id: int,
    article: dict,
    rule: sqlite3.Row,
    seen_at: str,
) -> int:
    paper_id = _resolve_target_paper(connection, article, rule)
    if paper_id is None:
        paper_id = _create_scholar_paper(connection, article, seen_at)
    connection.execute(
        """
        INSERT INTO researcher_papers (
            researcher_id, paper_id, scholar_citation_id,
            scholar_cited_by_count, scholar_last_seen_at,
            scholar_missing_since, source_match_status, source_match_score,
            missing_since
        ) VALUES (?, ?, ?, ?, ?, NULL, 'confirmed', 1.0, NULL)
        ON CONFLICT(researcher_id, paper_id) DO UPDATE SET
            scholar_citation_id=excluded.scholar_citation_id,
            scholar_cited_by_count=excluded.scholar_cited_by_count,
            scholar_last_seen_at=excluded.scholar_last_seen_at,
            scholar_missing_since=NULL,
            source_match_status='confirmed',
            source_match_score=1.0
        """,
        (
            researcher_id, paper_id, article['citation_id'],
            int(article.get('cited_by_count') or 0), seen_at,
        ),
    )
    paper = connection.execute(
        'SELECT openalex_id FROM papers WHERE id=?', (paper_id,)
    ).fetchone()
    if paper and not paper['openalex_id']:
        connection.execute(
            """
            UPDATE researcher_papers SET last_seen_at=NULL, missing_since=NULL
            WHERE researcher_id=? AND paper_id=?
            """,
            (researcher_id, paper_id),
        )
    if rule['target_openalex_id'] or rule['target_doi']:
        _hide_duplicate_versions(connection, paper_id, seen_at)
    return paper_id


def _resolve_target_paper(
    connection: sqlite3.Connection, article: dict, rule: sqlite3.Row
) -> int | None:
    row = None
    if rule['target_openalex_id']:
        row = connection.execute(
            'SELECT id FROM papers WHERE openalex_id=?',
            (rule['target_openalex_id'],),
        ).fetchone()
    if row is None and rule['target_doi']:
        row = connection.execute(
            'SELECT id FROM papers WHERE doi=?',
            (normalize_doi(rule['target_doi']),),
        ).fetchone()
    target_title = rule['target_normalized_title'] or normalize_title(article.get('title'))
    if row is None and target_title:
        rows = connection.execute(
            """
            SELECT id FROM papers WHERE normalized_title=?
            ORDER BY CASE WHEN doi IS NOT NULL AND doi <> '' THEN 0 ELSE 1 END, id
            """,
            (target_title,),
        ).fetchall()
        if len(rows) == 1:
            row = rows[0]
    return int(row['id']) if row else None


def _create_scholar_paper(
    connection: sqlite3.Connection, article: dict, seen_at: str
) -> int:
    title = str(article.get('title') or '').strip()
    normalized_title = normalize_title(title)
    if not normalized_title:
        raise ValueError('已确认 Scholar 论文缺少有效标题')
    publication = str(article.get('publication') or '').strip()
    work_type = 'conference' if 'conference' in publication.casefold() else 'journal'
    field, tags = classify({
        'title': title,
        'primary_location': {'source': {'display_name': publication}},
        'topics': [],
    })
    cursor = connection.execute(
        """
        INSERT INTO papers (
            normalized_title, title, authors, venue, publication_year,
            work_type, cited_by_count, field, tags_json,
            created_at, updated_at, last_seen_at, missing_since
        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, NULL, NULL)
        """,
        (
            normalized_title, title, str(article.get('authors') or ''), publication,
            int(article.get('year') or article.get('publication_year') or 0),
            work_type, field, json.dumps(tags, ensure_ascii=False), seen_at, seen_at,
        ),
    )
    return int(cursor.lastrowid)


def _hide_duplicate_versions(
    connection: sqlite3.Connection, canonical_paper_id: int, updated_at: str
) -> None:
    canonical = connection.execute(
        'SELECT normalized_title FROM papers WHERE id=?', (canonical_paper_id,)
    ).fetchone()
    if not canonical:
        return
    duplicate_rows = connection.execute(
        'SELECT id FROM papers WHERE normalized_title=? AND id<>?',
        (canonical['normalized_title'], canonical_paper_id),
    ).fetchall()
    for row in duplicate_rows:
        connection.execute(
            """
            INSERT INTO paper_overrides (paper_id, hidden, updated_at)
            VALUES (?, 1, ?)
            ON CONFLICT(paper_id) DO UPDATE SET hidden=1, updated_at=excluded.updated_at
            """,
            (row['id'], updated_at),
        )
    connection.execute(
        """
        INSERT INTO paper_overrides (paper_id, hidden, updated_at)
        VALUES (?, 0, ?)
        ON CONFLICT(paper_id) DO UPDATE SET hidden=0, updated_at=excluded.updated_at
        """,
        (canonical_paper_id, updated_at),
    )
