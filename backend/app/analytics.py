from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .config import Settings
from .database import connect


CHINA_TIMEZONE = timezone(timedelta(hours=8))
UTC = timezone.utc
PUBLIC_PATHS = frozenset({
    '/',
    '/achievements',
    '/contact',
    '/research',
    '/research/arm',
    '/research/diagnosis',
    '/research/drone',
    '/research/glove',
    '/research/hand',
    '/team',
})
BOT_PATTERN = re.compile(
    r'bot|crawler|spider|slurp|bingpreview|facebookexternalhit|'
    r'bytespider|headlesschrome|lighthouse|pagespeed|pingdom|uptimerobot',
    re.IGNORECASE,
)

ANALYTICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS analytics_totals (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    views INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics_daily (
    day TEXT PRIMARY KEY,
    views INTEGER NOT NULL DEFAULT 0,
    visitors INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS analytics_page_daily (
    day TEXT NOT NULL,
    path TEXT NOT NULL,
    views INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, path)
);

CREATE TABLE IF NOT EXISTS analytics_visitor_days (
    day TEXT NOT NULL,
    visitor_hash TEXT NOT NULL,
    first_seen_at INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,
    PRIMARY KEY (day, visitor_hash)
);

CREATE TABLE IF NOT EXISTS analytics_recent_views (
    day TEXT NOT NULL,
    visitor_hash TEXT NOT NULL,
    path TEXT NOT NULL,
    last_counted_at INTEGER NOT NULL,
    PRIMARY KEY (day, visitor_hash, path)
);

CREATE TABLE IF NOT EXISTS analytics_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS analytics_page_daily_day_idx
ON analytics_page_daily(day);
"""


def analytics_database_path(settings: Settings) -> Path:
    return settings.analytics_database_path or settings.database_path.with_name('analytics.db')


def initialize_analytics(settings: Settings, *, now: datetime | None = None) -> None:
    moment = _as_utc(now)
    day = _local_day(moment)
    timestamp = _iso_utc(moment)
    with connect(analytics_database_path(settings)) as connection:
        connection.executescript(ANALYTICS_SCHEMA)
        connection.execute(
            """
            INSERT OR IGNORE INTO analytics_totals(id, views, updated_at)
            VALUES (1, ?, ?)
            """,
            (settings.analytics_initial_total, timestamp),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO analytics_metadata(key, value)
            VALUES ('tracking_since', ?)
            """,
            (day,),
        )


def normalize_public_path(value: str | None) -> str | None:
    if not value or len(value) > 200:
        return None
    try:
        path = urlsplit(value).path
    except ValueError:
        return None
    if not path.startswith('/'):
        return None
    normalized = path.rstrip('/') or '/'
    return normalized if normalized in PUBLIC_PATHS else None


def is_probable_bot(user_agent: str | None) -> bool:
    return bool(BOT_PATTERN.search(user_agent or ''))


def record_pageview(
    settings: Settings,
    *,
    path: str,
    client_ip: str,
    user_agent: str,
    now: datetime | None = None,
) -> dict:
    normalized_path = normalize_public_path(path)
    if normalized_path is None:
        raise ValueError('无效的页面路径')
    if is_probable_bot(user_agent):
        return {'counted': False, 'reason': 'bot'}

    moment = _as_utc(now)
    day = _local_day(moment)
    timestamp = int(moment.timestamp())
    visitor_hash = _visitor_hash(settings, day, client_ip, user_agent)
    cutoff_day = (_local_date(moment) - timedelta(days=32)).isoformat()

    with connect(analytics_database_path(settings)) as connection:
        connection.execute('BEGIN IMMEDIATE')
        visitor_insert = connection.execute(
            """
            INSERT OR IGNORE INTO analytics_visitor_days(
                day, visitor_hash, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?)
            """,
            (day, visitor_hash, timestamp, timestamp),
        )
        is_new_visitor = visitor_insert.rowcount == 1
        connection.execute(
            """
            UPDATE analytics_visitor_days SET last_seen_at=?
            WHERE day=? AND visitor_hash=?
            """,
            (timestamp, day, visitor_hash),
        )

        recent = connection.execute(
            """
            SELECT last_counted_at FROM analytics_recent_views
            WHERE day=? AND visitor_hash=? AND path=?
            """,
            (day, visitor_hash, normalized_path),
        ).fetchone()
        if recent and timestamp - recent['last_counted_at'] < settings.analytics_dedupe_seconds:
            return {
                'counted': False,
                'reason': 'deduplicated',
                'newVisitor': False,
            }

        iso_timestamp = _iso_utc(moment)
        connection.execute(
            """
            UPDATE analytics_totals
            SET views=views + 1, updated_at=?
            WHERE id=1
            """,
            (iso_timestamp,),
        )
        connection.execute(
            """
            INSERT INTO analytics_daily(day, views, visitors)
            VALUES (?, 1, ?)
            ON CONFLICT(day) DO UPDATE SET
                views=analytics_daily.views + 1,
                visitors=analytics_daily.visitors + excluded.visitors
            """,
            (day, int(is_new_visitor)),
        )
        connection.execute(
            """
            INSERT INTO analytics_page_daily(day, path, views)
            VALUES (?, ?, 1)
            ON CONFLICT(day, path) DO UPDATE SET
                views=analytics_page_daily.views + 1
            """,
            (day, normalized_path),
        )
        connection.execute(
            """
            INSERT INTO analytics_recent_views(
                day, visitor_hash, path, last_counted_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(day, visitor_hash, path) DO UPDATE SET
                last_counted_at=excluded.last_counted_at
            """,
            (day, visitor_hash, normalized_path, timestamp),
        )
        connection.execute('DELETE FROM analytics_recent_views WHERE day < ?', (day,))
        connection.execute('DELETE FROM analytics_visitor_days WHERE day < ?', (cutoff_day,))

    return {'counted': True, 'newVisitor': is_new_visitor}


def get_analytics_summary(
    settings: Settings, *, now: datetime | None = None
) -> dict:
    moment = _as_utc(now)
    day = _local_day(moment)
    with connect(analytics_database_path(settings)) as connection:
        total = connection.execute(
            'SELECT views, updated_at FROM analytics_totals WHERE id=1'
        ).fetchone()
        daily = connection.execute(
            'SELECT views, visitors FROM analytics_daily WHERE day=?', (day,)
        ).fetchone()
        tracking_since = connection.execute(
            "SELECT value FROM analytics_metadata WHERE key='tracking_since'"
        ).fetchone()
    return {
        'totalViews': total['views'] if total else 0,
        'todayViews': daily['views'] if daily else 0,
        'todayVisitors': daily['visitors'] if daily else 0,
        'trackingSince': tracking_since['value'] if tracking_since else day,
        'updatedAt': total['updated_at'] if total else _iso_utc(moment),
    }


def make_analytics_etag(summary: dict) -> str:
    value = '|'.join(str(summary[key]) for key in sorted(summary))
    return f'"{hashlib.sha256(value.encode()).hexdigest()}"'


def _visitor_hash(
    settings: Settings, day: str, client_ip: str, user_agent: str
) -> str:
    secret = settings.analytics_hmac_secret or settings.sync_token
    if not secret:
        secret = 'eeglab-development-analytics-secret'
    message = '\0'.join((day, client_ip[:128], user_agent[:512])).encode('utf-8')
    return hmac.new(secret.encode('utf-8'), message, hashlib.sha256).hexdigest()


def _as_utc(value: datetime | None) -> datetime:
    moment = value or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def _local_date(value: datetime):
    return value.astimezone(CHINA_TIMEZONE).date()


def _local_day(value: datetime) -> str:
    return _local_date(value).isoformat()


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
