from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher

from .classification import classify
from .config import Settings
from .database import connect, normalize_doi, normalize_title, set_metadata, utc_now
from .openalex import fetch_author_works
from .scholar import ScholarProfile, fetch_author_profile
from .review_service import accept_scholar_article, load_review_rules


@dataclass
class SyncResult:
    run_id: int
    status: str
    fetched_count: int
    inserted_count: int
    updated_count: int
    missing_count: int
    snapshot_version: str | None
    scholar_fetched_count: int = 0
    scholar_matched_count: int = 0
    scholar_candidate_count: int = 0
    warnings: tuple[str, ...] = ()
    scholar_status: str = 'disabled'

    def as_dict(self) -> dict:
        return {
            'runId': self.run_id,
            'status': self.status,
            'fetchedCount': self.fetched_count,
            'insertedCount': self.inserted_count,
            'updatedCount': self.updated_count,
            'missingCount': self.missing_count,
            'snapshotVersion': self.snapshot_version,
            'sources': {
                'openalex': {'status': 'success', 'fetchedCount': self.fetched_count},
                'googleScholar': {
                    'status': self.scholar_status,
                    'fetchedCount': self.scholar_fetched_count,
                    'matchedCount': self.scholar_matched_count,
                    'candidateCount': self.scholar_candidate_count,
                },
            },
            'warnings': list(self.warnings),
        }


def sync_all_researchers(settings: Settings) -> SyncResult:
    started_at = utc_now()
    with connect(settings.database_path) as connection:
        cursor = connection.execute(
            "INSERT INTO sync_runs(started_at, status) VALUES (?, 'running')",
            (started_at,),
        )
        run_id = int(cursor.lastrowid)
        researchers = connection.execute(
            """
            SELECT id, slug, name, openalex_author_id, google_scholar_id
            FROM researchers
            WHERE active = 1 AND openalex_author_id IS NOT NULL
            ORDER BY sort_order, id
            """
        ).fetchall()

    try:
        if not researchers:
            raise RuntimeError('没有配置可同步的 OpenAlex 研究者')

        fetched_by_researcher: list[tuple[sqlite3.Row, list[dict]]] = []
        fetched_total = 0
        for researcher in researchers:
            works = fetch_author_works(
                researcher['openalex_author_id'], settings.openalex_api_key
            )
            _validate_count(settings, researcher, works)
            fetched_by_researcher.append((researcher, works))
            fetched_total += len(works)

        scholar_profiles: dict[int, ScholarProfile] = {}
        scholar_errors: dict[int, str] = {}
        warnings: list[str] = []
        if settings.serpapi_api_key:
            for researcher in researchers:
                scholar_id = researcher['google_scholar_id']
                if not scholar_id:
                    continue
                try:
                    profile = fetch_author_profile(
                        scholar_id, settings.serpapi_api_key
                    )
                    _validate_scholar_count(settings, researcher, profile)
                    scholar_profiles[researcher['id']] = profile
                except Exception as exc:
                    message = f'{researcher["name"]} 的 Google Scholar 同步失败: {exc}'
                    scholar_errors[researcher['id']] = str(exc)[:1000]
                    warnings.append(message)

        inserted_ids: set[int] = set()
        updated_ids: set[int] = set()
        missing_total = 0
        scholar_fetched_total = sum(len(item.articles) for item in scholar_profiles.values())
        scholar_matched_total = 0
        scholar_candidate_total = 0
        snapshot_version = utc_now()
        with connect(settings.database_path) as connection:
            connection.execute('BEGIN IMMEDIATE')
            for researcher, works in fetched_by_researcher:
                seen_ids: set[int] = set()
                for work in works:
                    paper_id, inserted = _upsert_work(connection, work, snapshot_version)
                    if inserted:
                        inserted_ids.add(paper_id)
                    else:
                        updated_ids.add(paper_id)
                    seen_ids.add(paper_id)
                    _upsert_researcher_link(
                        connection,
                        researcher_id=researcher['id'],
                        author_id=researcher['openalex_author_id'],
                        paper_id=paper_id,
                        work=work,
                        seen_at=snapshot_version,
                    )
                missing_total += _mark_missing_links(
                    connection, researcher['id'], seen_ids, snapshot_version
                )

                profile = scholar_profiles.get(researcher['id'])
                if profile:
                    matched, candidates = _reconcile_scholar(
                        connection, researcher['id'], profile, snapshot_version,
                        settings.scholar_match_threshold,
                    )
                    scholar_matched_total += matched
                    scholar_candidate_total += candidates
                    connection.execute(
                        """
                        UPDATE researchers SET scholar_total_citations=?, scholar_h_index=?,
                            scholar_i10_index=?, scholar_last_synced_at=?, scholar_sync_error=NULL,
                            updated_at=?
                        WHERE id=?
                        """,
                        (
                            profile.total_citations, profile.h_index, profile.i10_index,
                            snapshot_version, snapshot_version, researcher['id'],
                        ),
                    )
                elif researcher['id'] in scholar_errors:
                    connection.execute(
                        'UPDATE researchers SET scholar_sync_error=?, updated_at=? WHERE id=?',
                        (scholar_errors[researcher['id']], snapshot_version, researcher['id']),
                    )

            set_metadata(connection, 'snapshot_version', snapshot_version)
            set_metadata(connection, 'last_sync_at', snapshot_version)
            configured_scholar_ids = any(
                researcher['google_scholar_id'] for researcher in researchers
            )
            scholar_state = (
                'disabled' if not settings.serpapi_api_key else
                ('not_configured' if not configured_scholar_ids else
                 ('partial' if warnings else 'success'))
            )
            source_status = json.dumps({
                'openalex': 'success',
                'googleScholar': scholar_state,
                'warnings': warnings,
            }, ensure_ascii=False)
            connection.execute(
                """
                UPDATE sync_runs
                SET finished_at=?, status='success', fetched_count=?, inserted_count=?,
                    updated_count=?, missing_count=?, openalex_fetched_count=?,
                    scholar_fetched_count=?, scholar_matched_count=?,
                    scholar_candidate_count=?, source_status_json=?, snapshot_version=?
                WHERE id=?
                """,
                (
                    snapshot_version, fetched_total, len(inserted_ids), len(updated_ids),
                    missing_total, fetched_total, scholar_fetched_total,
                    scholar_matched_total, scholar_candidate_total, source_status,
                    snapshot_version, run_id,
                ),
            )
            connection.commit()
        return SyncResult(
            run_id, 'success', fetched_total, len(inserted_ids), len(updated_ids),
            missing_total, snapshot_version, scholar_fetched_total,
            scholar_matched_total, scholar_candidate_total, tuple(warnings),
            scholar_state,
        )
    except Exception as exc:
        finished_at = utc_now()
        with connect(settings.database_path) as connection:
            connection.execute(
                """
                UPDATE sync_runs
                SET finished_at=?, status='failed', error_message=?
                WHERE id=?
                """,
                (finished_at, str(exc)[:2000], run_id),
            )
        raise


def _validate_count(settings: Settings, researcher: sqlite3.Row, works: list[dict]) -> None:
    if not works:
        raise RuntimeError(f'{researcher["name"]} 的 OpenAlex 返回为空，拒绝覆盖快照')
    with connect(settings.database_path) as connection:
        existing = connection.execute(
            'SELECT COUNT(*) FROM researcher_papers WHERE researcher_id = ?',
            (researcher['id'],),
        ).fetchone()[0]
    minimum = int(existing * settings.sync_minimum_ratio)
    if existing and len(works) < minimum:
        raise RuntimeError(
            f'{researcher["name"]} 本次仅返回 {len(works)} 篇，'
            f'低于已有 {existing} 篇的安全阈值 {minimum} 篇'
        )


def _validate_scholar_count(
    settings: Settings, researcher: sqlite3.Row, profile: ScholarProfile
) -> None:
    if not profile.articles:
        raise RuntimeError('Scholar 返回空论文列表，保留上次核验快照')
    with connect(settings.database_path) as connection:
        confirmed = connection.execute(
            """
            SELECT COUNT(*) FROM researcher_papers
            WHERE researcher_id=? AND source_match_status='confirmed'
              AND scholar_missing_since IS NULL
            """,
            (researcher['id'],),
        ).fetchone()[0]
        candidates = connection.execute(
            """
            SELECT COUNT(*) FROM scholar_candidates
            WHERE researcher_id=? AND missing_since IS NULL
            """,
            (researcher['id'],),
        ).fetchone()[0]
    existing = confirmed + candidates
    minimum = int(existing * settings.scholar_minimum_ratio)
    if existing and len(profile.articles) < minimum:
        raise RuntimeError(
            f'Scholar 本次仅返回 {len(profile.articles)} 篇，'
            f'低于上次 {existing} 篇的安全阈值 {minimum} 篇'
        )


def _upsert_work(
    connection: sqlite3.Connection, work: dict, seen_at: str
) -> tuple[int, bool]:
    openalex_id = (work.get('id') or '').rsplit('/', 1)[-1] or None
    doi = normalize_doi(work.get('doi'))
    title = (work.get('title') or '').strip()
    if not title:
        raise RuntimeError(f'OpenAlex work {openalex_id or doi} 缺少标题')
    normalized_title = normalize_title(title)
    if not normalized_title:
        raise RuntimeError(f'论文标题无法标准化: {title!r}')

    row = None
    if openalex_id:
        row = connection.execute(
            'SELECT id FROM papers WHERE openalex_id = ?', (openalex_id,)
        ).fetchone()
    if row is None and doi:
        row = connection.execute('SELECT id FROM papers WHERE doi = ?', (doi,)).fetchone()
    if row is None:
        row = connection.execute(
            'SELECT id FROM papers WHERE normalized_title = ? ORDER BY id LIMIT 1',
            (normalized_title,),
        ).fetchone()

    authorships = work.get('authorships') or []
    authors = ', '.join(
        name for name in (
            ((authorship.get('author') or {}).get('display_name') or '').strip()
            for authorship in authorships
        ) if name
    )
    source = (work.get('primary_location') or {}).get('source') or {}
    venue = (source.get('display_name') or '').strip()
    source_type = (source.get('type') or '').lower()
    openalex_type = (work.get('type') or '').lower()
    work_type = 'conference' if (
        source_type == 'conference' or openalex_type in ('conference', 'proceedings-article')
    ) else 'journal'
    field, tags = classify(work)
    values = (
        openalex_id, doi, normalized_title, title, authors, venue,
        int(work.get('publication_year') or 0), work.get('publication_date'), work_type,
        int(work.get('cited_by_count') or 0), field,
        json.dumps(tags, ensure_ascii=False), seen_at, seen_at, None,
    )
    if row is None:
        cursor = connection.execute(
            """
            INSERT INTO papers (
                openalex_id, doi, normalized_title, title, authors, venue,
                publication_year, publication_date, work_type, cited_by_count,
                field, tags_json, created_at, updated_at, last_seen_at, missing_since
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*values[:12], seen_at, seen_at, seen_at, None),
        )
        return int(cursor.lastrowid), True

    paper_id = int(row['id'])
    connection.execute(
        """
        UPDATE papers SET
            openalex_id=COALESCE(?, openalex_id), doi=COALESCE(?, doi),
            normalized_title=?, title=?, authors=?, venue=?, publication_year=?,
            publication_date=?, work_type=?, cited_by_count=?, field=?, tags_json=?,
            updated_at=?, last_seen_at=?, missing_since=NULL
        WHERE id=?
        """,
        (
            openalex_id, doi, normalized_title, title, authors, venue,
            int(work.get('publication_year') or 0), work.get('publication_date'),
            work_type, int(work.get('cited_by_count') or 0), field,
            json.dumps(tags, ensure_ascii=False), seen_at, seen_at, paper_id,
        ),
    )
    return paper_id, False


def _upsert_researcher_link(
    connection: sqlite3.Connection,
    *,
    researcher_id: int,
    author_id: str,
    paper_id: int,
    work: dict,
    seen_at: str,
) -> None:
    position = None
    corresponding = False
    for index, authorship in enumerate(work.get('authorships') or [], start=1):
        current_id = ((authorship.get('author') or {}).get('id') or '').rsplit('/', 1)[-1]
        if current_id == author_id:
            position = index
            corresponding = bool(authorship.get('is_corresponding'))
            break
    connection.execute(
        """
        INSERT INTO researcher_papers (
            researcher_id, paper_id, author_position, is_corresponding,
            last_seen_at, missing_since
        ) VALUES (?, ?, ?, ?, ?, NULL)
        ON CONFLICT(researcher_id, paper_id) DO UPDATE SET
            author_position=excluded.author_position,
            is_corresponding=excluded.is_corresponding,
            last_seen_at=excluded.last_seen_at,
            missing_since=NULL
        """,
        (researcher_id, paper_id, position, int(corresponding), seen_at),
    )


def _mark_missing_links(
    connection: sqlite3.Connection,
    researcher_id: int,
    seen_ids: set[int],
    missing_at: str,
) -> int:
    rows = connection.execute(
        """
        SELECT paper_id FROM researcher_papers
        WHERE researcher_id = ? AND last_seen_at IS NOT NULL
        """,
        (researcher_id,),
    ).fetchall()
    missing_ids = [row['paper_id'] for row in rows if row['paper_id'] not in seen_ids]
    if missing_ids:
        placeholders = ','.join('?' for _ in missing_ids)
        connection.execute(
            f"""
            UPDATE researcher_papers
            SET missing_since=COALESCE(missing_since, ?)
            WHERE researcher_id=? AND paper_id IN ({placeholders})
            """,
            (missing_at, researcher_id, *missing_ids),
        )
    return len(missing_ids)


def _reconcile_scholar(
    connection: sqlite3.Connection,
    researcher_id: int,
    profile: ScholarProfile,
    seen_at: str,
    threshold: float,
) -> tuple[int, int]:
    paper_rows = connection.execute(
        """
        SELECT p.id, p.normalized_title, p.publication_year
        FROM researcher_papers rp
        JOIN papers p ON p.id = rp.paper_id
        WHERE rp.researcher_id=? AND rp.missing_since IS NULL
        """,
        (researcher_id,),
    ).fetchall()
    seen_paper_ids: set[int] = set()
    seen_candidate_ids: set[str] = set()
    review_rules = load_review_rules(connection, researcher_id)
    matched = 0
    candidates = 0
    for article in profile.articles:
        rule = review_rules.get(article['citation_id'])
        if rule and rule['decision'] == 'exclude':
            continue
        if rule and rule['decision'] == 'accept':
            paper_id = accept_scholar_article(
                connection, researcher_id, article, rule, seen_at
            )
            seen_paper_ids.add(paper_id)
            matched += 1
            continue
        available_rows = [row for row in paper_rows if row['id'] not in seen_paper_ids]
        paper_id, score, status = _match_scholar_article(article, available_rows, threshold)
        if paper_id is not None:
            connection.execute(
                """
                UPDATE researcher_papers SET scholar_citation_id=?,
                    scholar_cited_by_count=?, scholar_last_seen_at=?,
                    scholar_missing_since=NULL, source_match_status='confirmed',
                    source_match_score=?
                WHERE researcher_id=? AND paper_id=?
                """,
                (
                    article['citation_id'], article['cited_by_count'], seen_at, score,
                    researcher_id, paper_id,
                ),
            )
            seen_paper_ids.add(paper_id)
            matched += 1
            continue
        _upsert_scholar_candidate(
            connection, researcher_id, article, status, score, seen_at
        )
        seen_candidate_ids.add(article['citation_id'])
        candidates += 1

    confirmed_rows = connection.execute(
        """
        SELECT paper_id FROM researcher_papers
        WHERE researcher_id=? AND source_match_status='confirmed'
        """,
        (researcher_id,),
    ).fetchall()
    stale_ids = [row['paper_id'] for row in confirmed_rows if row['paper_id'] not in seen_paper_ids]
    if stale_ids:
        placeholders = ','.join('?' for _ in stale_ids)
        connection.execute(
            f"""
            UPDATE researcher_papers SET source_match_status='openalex_only',
                scholar_missing_since=COALESCE(scholar_missing_since, ?)
            WHERE researcher_id=? AND paper_id IN ({placeholders})
            """,
            (seen_at, researcher_id, *stale_ids),
        )

    candidate_rows = connection.execute(
        'SELECT citation_id FROM scholar_candidates WHERE researcher_id=?',
        (researcher_id,),
    ).fetchall()
    stale_candidates = [
        row['citation_id'] for row in candidate_rows
        if row['citation_id'] not in seen_candidate_ids
    ]
    if stale_candidates:
        placeholders = ','.join('?' for _ in stale_candidates)
        connection.execute(
            f"""
            UPDATE scholar_candidates SET missing_since=COALESCE(missing_since, ?)
            WHERE researcher_id=? AND citation_id IN ({placeholders})
            """,
            (seen_at, researcher_id, *stale_candidates),
        )
    return matched, candidates


def _match_scholar_article(
    article: dict, paper_rows: list[sqlite3.Row], threshold: float
) -> tuple[int | None, float, str]:
    title = normalize_title(article.get('title'))
    year = int(article.get('year') or 0)
    eligible = [
        row for row in paper_rows
        if not year or not row['publication_year'] or abs(year - row['publication_year']) <= 1
    ]
    exact = [row for row in eligible if row['normalized_title'] == title]
    if len(exact) == 1:
        return int(exact[0]['id']), 1.0, 'confirmed'
    if len(exact) > 1:
        return None, 1.0, 'ambiguous'
    scored = sorted(
        (
            (SequenceMatcher(None, title, row['normalized_title']).ratio(), row)
            for row in eligible
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if not scored:
        return None, 0.0, 'unmatched'
    best_score, best_row = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    if best_score >= threshold and best_score - runner_up >= 0.03:
        return int(best_row['id']), round(best_score, 4), 'confirmed'
    return None, round(best_score, 4), 'ambiguous' if best_score >= threshold else 'unmatched'


def _upsert_scholar_candidate(
    connection: sqlite3.Connection,
    researcher_id: int,
    article: dict,
    status: str,
    score: float,
    seen_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO scholar_candidates (
            researcher_id, citation_id, normalized_title, title, authors,
            publication, publication_year, cited_by_count, article_url,
            match_status, match_score, last_seen_at, missing_since
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        ON CONFLICT(researcher_id, citation_id) DO UPDATE SET
            normalized_title=excluded.normalized_title, title=excluded.title,
            authors=excluded.authors, publication=excluded.publication,
            publication_year=excluded.publication_year,
            cited_by_count=excluded.cited_by_count, article_url=excluded.article_url,
            match_status=excluded.match_status, match_score=excluded.match_score,
            last_seen_at=excluded.last_seen_at, missing_since=NULL
        """,
        (
            researcher_id, article['citation_id'], normalize_title(article['title']),
            article['title'], article['authors'], article['publication'], article['year'],
            article['cited_by_count'], article.get('link'), status, score, seen_at,
        ),
    )
