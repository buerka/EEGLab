from __future__ import annotations

import json
import re
import sqlite3
try:
    import tomllib
except ModuleNotFoundError:  # Makers Python 3.10
    import tomli as tomllib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Iterator

from .config import Settings

UTC = timezone.utc


SCHEMA = """
CREATE TABLE IF NOT EXISTS researchers (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    name_en TEXT,
    orcid TEXT,
    openalex_author_id TEXT UNIQUE,
    google_scholar_id TEXT,
    affiliation TEXT,
    avatar_url TEXT,
    scholar_total_citations INTEGER,
    scholar_h_index INTEGER,
    scholar_i10_index INTEGER,
    scholar_last_synced_at TEXT,
    scholar_sync_error TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY,
    openalex_id TEXT UNIQUE,
    doi TEXT,
    normalized_title TEXT NOT NULL,
    title TEXT NOT NULL,
    authors TEXT NOT NULL DEFAULT '',
    venue TEXT NOT NULL DEFAULT '',
    publication_year INTEGER NOT NULL DEFAULT 0,
    publication_date TEXT,
    work_type TEXT NOT NULL DEFAULT 'journal',
    cited_by_count INTEGER NOT NULL DEFAULT 0,
    field TEXT NOT NULL DEFAULT '其他',
    tags_json TEXT NOT NULL DEFAULT '["其他"]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_seen_at TEXT,
    missing_since TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS papers_doi_unique
ON papers(doi) WHERE doi IS NOT NULL AND doi <> '';
CREATE INDEX IF NOT EXISTS papers_normalized_title_idx ON papers(normalized_title);
CREATE INDEX IF NOT EXISTS papers_year_idx ON papers(publication_year DESC);

CREATE TABLE IF NOT EXISTS researcher_papers (
    researcher_id INTEGER NOT NULL REFERENCES researchers(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    author_position INTEGER,
    is_corresponding INTEGER NOT NULL DEFAULT 0,
    last_seen_at TEXT,
    missing_since TEXT,
    scholar_citation_id TEXT,
    scholar_cited_by_count INTEGER,
    scholar_last_seen_at TEXT,
    scholar_missing_since TEXT,
    source_match_status TEXT NOT NULL DEFAULT 'openalex_only',
    source_match_score REAL,
    PRIMARY KEY (researcher_id, paper_id)
);

CREATE TABLE IF NOT EXISTS scholar_candidates (
    id INTEGER PRIMARY KEY,
    researcher_id INTEGER NOT NULL REFERENCES researchers(id) ON DELETE CASCADE,
    citation_id TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    title TEXT NOT NULL,
    authors TEXT NOT NULL DEFAULT '',
    publication TEXT NOT NULL DEFAULT '',
    publication_year INTEGER NOT NULL DEFAULT 0,
    cited_by_count INTEGER NOT NULL DEFAULT 0,
    article_url TEXT,
    match_status TEXT NOT NULL DEFAULT 'unmatched',
    match_score REAL,
    last_seen_at TEXT NOT NULL,
    missing_since TEXT,
    UNIQUE(researcher_id, citation_id)
);
CREATE INDEX IF NOT EXISTS scholar_candidates_researcher_idx
ON scholar_candidates(researcher_id, match_status);

CREATE TABLE IF NOT EXISTS scholar_review_rules (
    researcher_id INTEGER NOT NULL REFERENCES researchers(id) ON DELETE CASCADE,
    citation_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('accept', 'exclude')),
    target_openalex_id TEXT,
    target_doi TEXT,
    target_normalized_title TEXT,
    notes TEXT,
    reviewed_at TEXT NOT NULL,
    PRIMARY KEY (researcher_id, citation_id)
);

CREATE TABLE IF NOT EXISTS paper_overrides (
    paper_id INTEGER PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
    quartile TEXT,
    impact_factor REAL,
    is_top INTEGER,
    field_override TEXT,
    tags_override_json TEXT,
    hidden INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS researcher_paper_overrides (
    researcher_id INTEGER NOT NULL REFERENCES researchers(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    representative INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (researcher_id, paper_id)
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    fetched_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    missing_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    openalex_fetched_count INTEGER NOT NULL DEFAULT 0,
    scholar_fetched_count INTEGER NOT NULL DEFAULT 0,
    scholar_matched_count INTEGER NOT NULL DEFAULT 0,
    scholar_candidate_count INTEGER NOT NULL DEFAULT 0,
    source_status_json TEXT NOT NULL DEFAULT '{}',
    snapshot_version TEXT
);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def normalize_doi(value: str | None) -> str | None:
    normalized = (value or '').lower().strip()
    for prefix in ('https://doi.org/', 'http://doi.org/', 'doi:'):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    return normalized or None


def normalize_title(value: str | None) -> str:
    # 保留所有 Unicode 字母和数字，避免中文标题全部归一化为空字符串。
    return ''.join(char for char in (value or '').casefold() if char.isalnum())


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    connection.execute('PRAGMA journal_mode = WAL')
    connection.execute('PRAGMA busy_timeout = 30000')
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(settings: Settings) -> None:
    with connect(settings.database_path) as connection:
        connection.executescript(SCHEMA)
        _migrate_schema(connection)
        _seed_researchers(connection, settings.researchers_seed_path)
        _seed_papers(connection, settings.papers_seed_path)
        _seed_scholar_reviews(connection, settings.scholar_reviews_seed_path)
    # 延迟导入避免 database ↔ review_service 的模块循环。
    from .review_service import apply_scholar_review_rules
    apply_scholar_review_rules(settings)


def _migrate_schema(connection: sqlite3.Connection) -> None:
    """为已有 SQLite 数据库做幂等的增量升级。"""
    additions = {
        'researchers': {
            'scholar_total_citations': 'INTEGER',
            'scholar_h_index': 'INTEGER',
            'scholar_i10_index': 'INTEGER',
            'scholar_last_synced_at': 'TEXT',
            'scholar_sync_error': 'TEXT',
        },
        'researcher_papers': {
            'scholar_citation_id': 'TEXT',
            'scholar_cited_by_count': 'INTEGER',
            'scholar_last_seen_at': 'TEXT',
            'scholar_missing_since': 'TEXT',
            'source_match_status': "TEXT NOT NULL DEFAULT 'openalex_only'",
            'source_match_score': 'REAL',
        },
        'sync_runs': {
            'openalex_fetched_count': 'INTEGER NOT NULL DEFAULT 0',
            'scholar_fetched_count': 'INTEGER NOT NULL DEFAULT 0',
            'scholar_matched_count': 'INTEGER NOT NULL DEFAULT 0',
            'scholar_candidate_count': 'INTEGER NOT NULL DEFAULT 0',
            'source_status_json': "TEXT NOT NULL DEFAULT '{}'",
        },
    }
    for table, columns in additions.items():
        existing = {
            row['name'] for row in connection.execute(f'PRAGMA table_info({table})')
        }
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')


def _seed_researchers(connection: sqlite3.Connection, path: Path) -> None:
    if not path.exists():
        return
    data = tomllib.loads(path.read_text(encoding='utf-8'))
    now = utc_now()
    for item in data.get('researchers', []):
        connection.execute(
            """
            INSERT INTO researchers (
                slug, name, name_en, orcid, openalex_author_id, google_scholar_id,
                affiliation, avatar_url, active, sort_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name,
                name_en=excluded.name_en,
                orcid=excluded.orcid,
                openalex_author_id=excluded.openalex_author_id,
                google_scholar_id=excluded.google_scholar_id,
                affiliation=excluded.affiliation,
                avatar_url=excluded.avatar_url,
                active=excluded.active,
                sort_order=excluded.sort_order,
                updated_at=excluded.updated_at
            """,
            (
                item['slug'], item['name'], item.get('name_en'), item.get('orcid'),
                item.get('openalex_author_id'), item.get('google_scholar_id'),
                item.get('affiliation'), item.get('avatar_url'),
                int(item.get('active', True)), int(item.get('sort_order', 0)), now, now,
            ),
        )


def _seed_papers(connection: sqlite3.Connection, path: Path) -> None:
    if not path.exists():
        return
    existing = connection.execute('SELECT COUNT(*) FROM papers').fetchone()[0]
    if existing:
        return
    researcher = connection.execute(
        "SELECT id FROM researchers WHERE slug = 'ying-yan'"
    ).fetchone()
    if not researcher:
        return
    researcher_id = researcher['id']
    data = tomllib.loads(path.read_text(encoding='utf-8'))
    now = utc_now()
    for item in data.get('papers', []):
        cursor = connection.execute(
            """
            INSERT INTO papers (
                doi, normalized_title, title, authors, venue, publication_year,
                work_type, field, tags_json, created_at, updated_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalize_doi(item.get('doi')), normalize_title(item.get('title')),
                item.get('title', 'Untitled'), item.get('authors', ''), item.get('journal', ''),
                int(item.get('year', 0)), item.get('type', 'journal'),
                item.get('field', '其他'), json.dumps(item.get('tags') or ['其他'], ensure_ascii=False),
                now, now, now,
            ),
        )
        paper_id = cursor.lastrowid
        connection.execute(
            """
            INSERT INTO researcher_papers (
                researcher_id, paper_id, author_position, is_corresponding, last_seen_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (researcher_id, paper_id, None, int(item.get('lead', False)), now),
        )
        connection.execute(
            """
            INSERT INTO paper_overrides (
                paper_id, quartile, impact_factor, is_top, field_override,
                tags_override_json, hidden, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                paper_id, item.get('quartile'), item.get('impactFactor'),
                int(item.get('isTop', False)), item.get('field'),
                json.dumps(item.get('tags') or ['其他'], ensure_ascii=False), now,
            ),
        )
        if item.get('representative'):
            connection.execute(
                """
                INSERT INTO researcher_paper_overrides (
                    researcher_id, paper_id, representative, updated_at
                ) VALUES (?, ?, 1, ?)
                """,
                (researcher_id, paper_id, now),
            )
    connection.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES ('snapshot_version', ?)",
        (now,),
    )
    connection.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES ('last_sync_at', ?)",
        (now,),
    )


def _seed_scholar_reviews(
    connection: sqlite3.Connection, path: Path | None
) -> None:
    if not path or not path.exists():
        return
    data = tomllib.loads(path.read_text(encoding='utf-8'))
    now = utc_now()
    for item in data.get('reviews', []):
        researcher = connection.execute(
            'SELECT id FROM researchers WHERE slug=?',
            (item['researcher_slug'],),
        ).fetchone()
        if not researcher:
            continue
        decision = item.get('decision')
        if decision not in ('accept', 'exclude'):
            raise ValueError(f'无效 Scholar 审核决定: {decision!r}')
        target_openalex_id = (item.get('target_openalex_id') or '').rsplit('/', 1)[-1] or None
        connection.execute(
            """
            INSERT INTO scholar_review_rules (
                researcher_id, citation_id, decision, target_openalex_id,
                target_doi, target_normalized_title, notes, reviewed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(researcher_id, citation_id) DO UPDATE SET
                decision=excluded.decision,
                target_openalex_id=excluded.target_openalex_id,
                target_doi=excluded.target_doi,
                target_normalized_title=excluded.target_normalized_title,
                notes=excluded.notes,
                reviewed_at=excluded.reviewed_at
            """,
            (
                researcher['id'], item['citation_id'], decision, target_openalex_id,
                normalize_doi(item.get('target_doi')),
                normalize_title(item.get('target_title')) or None,
                item.get('notes'), now,
            ),
        )
    for item in data.get('paper_merges', []):
        canonical_doi = normalize_doi(item.get('canonical_doi'))
        canonical = connection.execute(
            'SELECT id FROM papers WHERE doi=?', (canonical_doi,)
        ).fetchone()
        if canonical:
            connection.execute(
                """
                INSERT INTO paper_overrides (paper_id, hidden, notes, updated_at)
                VALUES (?, 0, ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET
                    hidden=0, notes=COALESCE(excluded.notes, paper_overrides.notes),
                    updated_at=excluded.updated_at
                """,
                (canonical['id'], item.get('notes'), now),
            )
        for duplicate_doi in item.get('duplicate_dois', []):
            duplicate = connection.execute(
                'SELECT id FROM papers WHERE doi=?', (normalize_doi(duplicate_doi),)
            ).fetchone()
            if duplicate:
                connection.execute(
                    """
                    INSERT INTO paper_overrides (paper_id, hidden, notes, updated_at)
                    VALUES (?, 1, ?, ?)
                    ON CONFLICT(paper_id) DO UPDATE SET
                        hidden=1, notes=COALESCE(excluded.notes, paper_overrides.notes),
                        updated_at=excluded.updated_at
                    """,
                    (duplicate['id'], item.get('notes'), now),
                )


def get_metadata(connection: sqlite3.Connection, key: str, default: str = '') -> str:
    row = connection.execute('SELECT value FROM metadata WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default


def set_metadata(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        'INSERT INTO metadata(key, value) VALUES (?, ?) '
        'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
        (key, value),
    )
