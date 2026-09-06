from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
from pathlib import Path

from starlette.testclient import TestClient

from app.analytics import (
    get_analytics_summary,
    initialize_analytics,
    normalize_public_path,
    record_pageview,
)
from app.config import BACKEND_ROOT, Settings
from app.database import connect


class AnalyticsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.settings = Settings(
            database_path=root / 'papers.db',
            researchers_seed_path=BACKEND_ROOT / 'data' / 'researchers.toml',
            papers_seed_path=BACKEND_ROOT / 'data' / 'papers.toml',
            openalex_api_key=None,
            sync_token='test-sync-token',
            allowed_origins=('http://localhost:4321',),
            cache_control='public, max-age=0, s-maxage=60',
            sync_interval_seconds=86400,
            sync_minimum_ratio=0.8,
            analytics_database_path=root / 'analytics.db',
            analytics_hmac_secret='test-analytics-secret',
            analytics_cache_control=(
                'public, max-age=15, s-maxage=60, stale-while-revalidate=300'
            ),
            analytics_dedupe_seconds=30,
        )
        self.now = datetime(2026, 8, 4, 2, 0, tzinfo=UTC)
        initialize_analytics(self.settings, now=self.now)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_aggregates_views_without_storing_raw_ip(self) -> None:
        first = record_pageview(
            self.settings,
            path='/',
            client_ip='203.0.113.10',
            user_agent='Real Browser/1.0',
            now=self.now,
        )
        duplicate = record_pageview(
            self.settings,
            path='/',
            client_ip='203.0.113.10',
            user_agent='Real Browser/1.0',
            now=self.now + timedelta(seconds=10),
        )
        second_page = record_pageview(
            self.settings,
            path='/team?from=home',
            client_ip='203.0.113.10',
            user_agent='Real Browser/1.0',
            now=self.now + timedelta(seconds=15),
        )
        second_visitor = record_pageview(
            self.settings,
            path='/',
            client_ip='203.0.113.11',
            user_agent='Another Browser/2.0',
            now=self.now + timedelta(seconds=20),
        )
        bot = record_pageview(
            self.settings,
            path='/',
            client_ip='203.0.113.12',
            user_agent='ExampleBot/1.0',
            now=self.now + timedelta(seconds=25),
        )

        self.assertEqual(first, {'counted': True, 'newVisitor': True})
        self.assertEqual(duplicate['reason'], 'deduplicated')
        self.assertEqual(second_page, {'counted': True, 'newVisitor': False})
        self.assertEqual(second_visitor, {'counted': True, 'newVisitor': True})
        self.assertEqual(bot, {'counted': False, 'reason': 'bot'})

        summary = get_analytics_summary(self.settings, now=self.now)
        self.assertEqual(summary['totalViews'], 3)
        self.assertEqual(summary['todayViews'], 3)
        self.assertEqual(summary['todayVisitors'], 2)
        self.assertEqual(summary['trackingSince'], '2026-08-04')

        with connect(self.settings.analytics_database_path) as connection:
            hashes = [
                row['visitor_hash']
                for row in connection.execute(
                    'SELECT visitor_hash FROM analytics_visitor_days'
                )
            ]
            columns = {
                row['name']
                for row in connection.execute('PRAGMA table_info(analytics_visitor_days)')
            }
        self.assertEqual(len(hashes), 2)
        self.assertTrue(all(len(value) == 64 for value in hashes))
        self.assertNotIn('203.0.113.10', ''.join(hashes))
        self.assertNotIn('ip', columns)

    def test_validates_public_paths(self) -> None:
        self.assertEqual(normalize_public_path('/research/arm/?source=test'), '/research/arm')
        self.assertEqual(normalize_public_path('/'), '/')
        self.assertIsNone(normalize_public_path('/api/papers'))
        self.assertIsNone(normalize_public_path('/images/logo.webp'))
        self.assertIsNone(normalize_public_path('team'))

    def test_api_origin_deduplication_cache_and_etag(self) -> None:
        from app import main

        original_settings = main.settings
        main.settings = self.settings
        try:
            with TestClient(main.app) as client:
                headers = {
                    'Origin': 'http://localhost:4321',
                    'User-Agent': 'Real Browser/1.0',
                    'X-Forwarded-For': '198.51.100.20, 127.0.0.1',
                }
                first = client.post(
                    '/api/analytics/pageview', json={'path': '/'}, headers=headers
                )
                duplicate = client.post(
                    '/api/analytics/pageview', json={'path': '/'}, headers=headers
                )
                self.assertEqual(first.status_code, 204)
                self.assertEqual(duplicate.status_code, 204)
                self.assertEqual(first.headers['cache-control'], 'no-store')

                summary = client.get('/api/analytics/summary')
                self.assertEqual(summary.status_code, 200)
                self.assertEqual(summary.json()['totalViews'], 1)
                self.assertEqual(summary.json()['todayVisitors'], 1)
                self.assertEqual(
                    summary.headers['cache-control'],
                    self.settings.analytics_cache_control,
                )
                self.assertIn('etag', summary.headers)
                unchanged = client.get(
                    '/api/analytics/summary',
                    headers={'If-None-Match': summary.headers['etag']},
                )
                self.assertEqual(unchanged.status_code, 304)

                forbidden = client.post(
                    '/api/analytics/pageview',
                    json={'path': '/'},
                    headers={**headers, 'Origin': 'https://attacker.example'},
                )
                invalid = client.post(
                    '/api/analytics/pageview',
                    json={'path': '/api/admin/sync'},
                    headers=headers,
                )
                self.assertEqual(forbidden.status_code, 403)
                self.assertEqual(invalid.status_code, 400)
        finally:
            main.settings = original_settings


if __name__ == '__main__':
    unittest.main()
