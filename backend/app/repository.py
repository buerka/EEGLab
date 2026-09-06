from __future__ import annotations

import hashlib
import json
import sqlite3
from .config import Settings
from .database import connect, get_metadata, utc_now


def list_researchers(settings: Settings) -> list[dict]:
    with connect(settings.database_path) as connection:
        rows = connection.execute(
            """
            SELECT r.*,
                   COUNT(CASE
                       WHEN rp.paper_id IS NOT NULL AND COALESCE(po.hidden, 0) = 0
                       THEN 1
                   END) AS paper_count,
                   COUNT(CASE
                       WHEN rp.paper_id IS NOT NULL
                        AND rp.missing_since IS NULL
                        AND COALESCE(po.hidden, 0) = 0
                       THEN 1
                   END) AS current_count
            FROM researchers r
            LEFT JOIN researcher_papers rp ON rp.researcher_id = r.id
            LEFT JOIN paper_overrides po ON po.paper_id = rp.paper_id
            WHERE r.active = 1
            GROUP BY r.id
            ORDER BY r.sort_order, r.id
            """
        ).fetchall()
    return [_researcher_dict(row) for row in rows]


def get_publications(settings: Settings, filters: dict) -> dict:
    with connect(settings.database_path) as connection:
        snapshot_version = get_metadata(connection, 'snapshot_version', '')
        last_sync_at = get_metadata(connection, 'last_sync_at', '')
        paper_rows = connection.execute(
            """
            SELECT p.*,
                   po.quartile,
                   po.impact_factor,
                   COALESCE(po.is_top, 0) AS is_top,
                   COALESCE(po.field_override, p.field) AS resolved_field,
                   COALESCE(po.tags_override_json, p.tags_json) AS resolved_tags_json
            FROM papers p
            LEFT JOIN paper_overrides po ON po.paper_id = p.id
            WHERE COALESCE(po.hidden, 0) = 0
            ORDER BY p.publication_year DESC,
                     COALESCE(p.publication_date, '') DESC,
                     p.title COLLATE NOCASE
            """
        ).fetchall()
        link_rows = connection.execute(
            """
            SELECT rp.paper_id, rp.author_position, rp.is_corresponding,
                   rp.missing_since, rp.scholar_citation_id,
                   rp.scholar_cited_by_count, rp.scholar_last_seen_at,
                   rp.scholar_missing_since, rp.source_match_status,
                   rp.source_match_score, r.id AS researcher_id, r.slug, r.name,
                   r.name_en, r.avatar_url,
                   COALESCE(rpo.representative, 0) AS representative
            FROM researcher_papers rp
            JOIN researchers r ON r.id = rp.researcher_id AND r.active = 1
            LEFT JOIN researcher_paper_overrides rpo
              ON rpo.researcher_id = rp.researcher_id AND rpo.paper_id = rp.paper_id
            ORDER BY r.sort_order, r.id
            """
        ).fetchall()

    links_by_paper: dict[int, list[dict]] = {}
    for row in link_rows:
        links_by_paper.setdefault(row['paper_id'], []).append({
            'id': row['researcher_id'],
            'slug': row['slug'],
            'name': row['name'],
            'nameEn': row['name_en'],
            'avatarUrl': row['avatar_url'],
            'authorPosition': row['author_position'],
            'isCorresponding': bool(row['is_corresponding']),
            'representative': bool(row['representative']),
            'missingSince': row['missing_since'],
            'scholarCitationId': row['scholar_citation_id'],
            'scholarCitedByCount': row['scholar_cited_by_count'],
            'scholarLastSeenAt': row['scholar_last_seen_at'],
            'scholarMissingSince': row['scholar_missing_since'],
            'sourceMatchStatus': row['source_match_status'],
            'sourceMatchScore': row['source_match_score'],
        })

    requested_researchers = set(filters.get('researchers') or [])
    papers: list[dict] = []
    for row in paper_rows:
        researcher_links = links_by_paper.get(row['id'], [])
        if not researcher_links:
            continue
        selected_links = [
            link for link in researcher_links
            if not requested_researchers or link['slug'] in requested_researchers
        ]
        if requested_researchers and not selected_links:
            continue
        tags = json.loads(row['resolved_tags_json'] or '[]')
        if filters.get('tag') and filters['tag'] not in tags:
            continue
        if filters.get('field') and filters['field'] != row['resolved_field']:
            continue
        if filters.get('year') and filters['year'] != row['publication_year']:
            continue
        representative = any(link['representative'] for link in selected_links or researcher_links)
        if filters.get('representative') is True and not representative:
            continue
        query = (filters.get('query') or '').casefold()
        if query and query not in f'{row["title"]} {row["authors"]} {row["venue"]}'.casefold():
            continue
        relevant_links = selected_links or researcher_links
        scholar_counts = [
            link['scholarCitedByCount'] for link in relevant_links
            if link['sourceMatchStatus'] == 'confirmed'
            and link['scholarCitedByCount'] is not None
        ]
        scholar_count = max(scholar_counts) if scholar_counts else None
        has_confirmed_scholar = any(
            link['sourceMatchStatus'] == 'confirmed' for link in relevant_links
        )
        source_status = (
            ('confirmed' if row['openalex_id'] else 'scholar_only')
            if has_confirmed_scholar else 'openalex_only'
        )
        papers.append({
            'id': row['openalex_id'] or f'local-{row["id"]}',
            'doi': row['doi'],
            'year': row['publication_year'],
            'publicationDate': row['publication_date'],
            'title': row['title'],
            'authors': row['authors'],
            'journal': row['venue'],
            'type': row['work_type'],
            'citedByCount': scholar_count if scholar_count is not None else row['cited_by_count'],
            'citationSource': 'googleScholar' if scholar_count is not None else 'openalex',
            'citationSources': {
                'openalex': row['cited_by_count'] if row['openalex_id'] else None,
                'googleScholar': scholar_count,
            },
            'sourceStatus': source_status,
            'field': row['resolved_field'],
            'tags': tags,
            'quartile': row['quartile'],
            'impactFactor': row['impact_factor'],
            'isTop': bool(row['is_top']),
            'lead': any(
                link['isCorresponding'] or link['authorPosition'] == 1
                for link in selected_links or researcher_links
            ),
            'representative': representative,
            'researchers': researcher_links,
        })

    total = len(papers)
    offset = max(0, int(filters.get('offset') or 0))
    limit = min(500, max(1, int(filters.get('limit') or 500)))
    page = papers[offset:offset + limit]
    for index, paper in enumerate(page, start=offset + 1):
        paper['num'] = f'{index:02d}'
    return {
        'version': snapshot_version,
        'updatedAt': last_sync_at,
        'total': total,
        'typeCounts': {
            'journal': sum(paper['type'] == 'journal' for paper in papers),
            'conference': sum(paper['type'] == 'conference' for paper in papers),
        },
        'offset': offset,
        'limit': limit,
        'filterTags': sorted({tag for paper in papers for tag in paper['tags']}),
        'fields': sorted({paper['field'] for paper in papers}),
        'years': sorted({paper['year'] for paper in papers if paper['year']}, reverse=True),
        'researchers': list_researchers(settings),
        'papers': page,
    }


def get_sync_status(settings: Settings) -> dict:
    with connect(settings.database_path) as connection:
        row = connection.execute(
            'SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1'
        ).fetchone()
        snapshot_version = get_metadata(connection, 'snapshot_version', '')
        last_sync_at = get_metadata(connection, 'last_sync_at', '')
    if not row:
        return {
            'status': 'never', 'snapshotVersion': snapshot_version,
            'lastSyncAt': last_sync_at,
        }
    return {
        'runId': row['id'],
        'status': row['status'],
        'startedAt': row['started_at'],
        'finishedAt': row['finished_at'],
        'fetchedCount': row['fetched_count'],
        'insertedCount': row['inserted_count'],
        'updatedCount': row['updated_count'],
        'missingCount': row['missing_count'],
        'sources': _source_status(row),
        'error': row['error_message'],
        'snapshotVersion': snapshot_version,
        'lastSyncAt': last_sync_at,
    }


def list_scholar_candidates(settings: Settings) -> list[dict]:
    with connect(settings.database_path) as connection:
        rows = connection.execute(
            """
            SELECT sc.*, r.slug AS researcher_slug, r.name AS researcher_name
            FROM scholar_candidates sc
            JOIN researchers r ON r.id = sc.researcher_id
              WHERE sc.missing_since IS NULL
                AND NOT EXISTS (
                    SELECT 1 FROM scholar_review_rules rr
                    WHERE rr.researcher_id=sc.researcher_id
                      AND rr.citation_id=sc.citation_id
                )
            ORDER BY CASE sc.match_status WHEN 'ambiguous' THEN 0 ELSE 1 END,
                     sc.match_score DESC, sc.publication_year DESC, sc.title
            """
        ).fetchall()
    return [{
        'id': row['id'],
        'researcher': {
            'slug': row['researcher_slug'], 'name': row['researcher_name'],
        },
        'citationId': row['citation_id'],
        'title': row['title'],
        'authors': row['authors'],
        'publication': row['publication'],
        'year': row['publication_year'],
        'citedByCount': row['cited_by_count'],
        'url': row['article_url'],
        'matchStatus': row['match_status'],
        'matchScore': row['match_score'],
        'lastSeenAt': row['last_seen_at'],
    } for row in rows]


def create_researcher(settings: Settings, payload: dict) -> dict:
    required = ('slug', 'name', 'openalexAuthorId')
    missing = [key for key in required if not str(payload.get(key) or '').strip()]
    if missing:
        raise ValueError(f'缺少字段: {", ".join(missing)}')
    slug = str(payload['slug']).strip().lower()
    if not all(char.isalnum() or char == '-' for char in slug):
        raise ValueError('slug 只能包含小写字母、数字和连字符')
    now = utc_now()
    with connect(settings.database_path) as connection:
        connection.execute(
            """
            INSERT INTO researchers (
                slug, name, name_en, orcid, openalex_author_id, google_scholar_id,
                affiliation, avatar_url, active, sort_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                slug, str(payload['name']).strip(), payload.get('nameEn'), payload.get('orcid'),
                str(payload['openalexAuthorId']).strip().rsplit('/', 1)[-1],
                payload.get('googleScholarId'), payload.get('affiliation'),
                payload.get('avatarUrl'), int(payload.get('sortOrder', 100)), now, now,
            ),
        )
    return next(item for item in list_researchers(settings) if item['slug'] == slug)


def make_etag(version: str, query_string: str) -> str:
    digest = hashlib.sha256(f'{version}|{query_string}'.encode()).hexdigest()[:20]
    return f'"papers-{digest}"'


def _researcher_dict(row: sqlite3.Row) -> dict:
    scholar_id = row['google_scholar_id']
    return {
        'id': row['id'],
        'slug': row['slug'],
        'name': row['name'],
        'nameEn': row['name_en'],
        'orcid': row['orcid'],
        'openalexAuthorId': row['openalex_author_id'],
        'googleScholarId': scholar_id,
        'googleScholarUrl': (
            f'https://scholar.google.com/citations?user={scholar_id}' if scholar_id else None
        ),
        'affiliation': row['affiliation'],
        'avatarUrl': row['avatar_url'],
        'paperCount': int(row['paper_count'] or 0),
        'currentPaperCount': int(row['current_count'] or 0),
        'scholarMetrics': {
            'totalCitations': row['scholar_total_citations'],
            'hIndex': row['scholar_h_index'],
            'i10Index': row['scholar_i10_index'],
            'updatedAt': row['scholar_last_synced_at'],
            'status': (
                'success' if row['scholar_last_synced_at'] and not row['scholar_sync_error']
                else ('warning' if row['scholar_sync_error'] else 'pending')
            ),
        },
    }


def _source_status(row: sqlite3.Row) -> dict:
    try:
        status = json.loads(row['source_status_json'] or '{}')
    except json.JSONDecodeError:
        status = {}
    status.setdefault('openalex', 'unknown')
    status.setdefault('googleScholar', 'disabled')
    status['counts'] = {
        'openalexFetched': row['openalex_fetched_count'],
        'scholarFetched': row['scholar_fetched_count'],
        'scholarMatched': row['scholar_matched_count'],
        'scholarCandidates': row['scholar_candidate_count'],
    }
    return status
