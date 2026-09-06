from __future__ import annotations

import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.budget import sync_budget, remaining_timeout, retry_sleep, SyncDeadlineExceeded
from app.cloud_api import dispatch
from app.cloud_analytics import record_cloud_pageview, get_cloud_summary, rollup_analytics
from app.cloud_papers import paper_workspace
from app.cloud_runtime import sync_cloud, latest_run, scheduled_job
from app.config import Settings, BACKEND_ROOT
from app.cos_store import WriteConflict, StorageError
from app.repository import create_researcher, list_researchers


class MemoryStore:
    def __init__(self):
        self.objects = {}
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            return self.objects.get(key)

    def create(self, key, value):
        with self.lock:
            if key in self.objects:
                raise WriteConflict(key)
            self.objects[key] = value

    def list(self, prefix, *, limit=None, marker=''):
        with self.lock:
            keys = sorted(key for key in self.objects if key.startswith(prefix) and key > marker)
            return keys[:limit] if limit else keys

    def delete(self, keys):
        with self.lock:
            for key in keys:
                self.objects.pop(key, None)


def settings():
    return Settings(database_path=Path('unused.db'),
                    researchers_seed_path=BACKEND_ROOT / 'data/researchers.toml',
                    papers_seed_path=BACKEND_ROOT / 'data/papers.toml',
                    scholar_reviews_seed_path=BACKEND_ROOT / 'data/scholar_reviews.toml',
                    openalex_api_key=None, sync_token='x' * 40,
                    allowed_origins=('https://lab.example.cn',),
                    cache_control='public, max-age=0, s-maxage=60',
                    sync_interval_seconds=86400, sync_minimum_ratio=0.8,
                    analytics_hmac_secret='y' * 40, analytics_initial_total=100)


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.settings = settings()

    def call(self, method, path, *, payload=None, admin=False, headers=None):
        values = {'host': 'lab.example.cn', **(headers or {})}
        if admin:
            values['authorization'] = 'Bearer ' + self.settings.sync_token
        status, response_headers, body = dispatch(
            method, path, values, json.dumps(payload).encode() if payload is not None else b'',
            store=self.store, settings=self.settings)
        return status, response_headers, json.loads(body) if body else None

    def test_cold_start_seed_etag_and_api_prefix(self):
        code, headers, data = self.call('GET', '/api/papers')
        self.assertEqual(code, 200)
        # Production review seeds hide a duplicate DOI, leaving 135 public papers.
        self.assertEqual(data['total'], 135)
        self.assertTrue(data['version'].startswith('seed-'))
        self.assertEqual(self.call('GET', '/papers', headers={'if-none-match': headers['ETag']})[0], 304)
        self.assertEqual(len(self.store.objects), 0)
        self.assertEqual(self.call('GET', '/api/papers?representative=true&limit=1')[2]['total'], 3)
        self.assertEqual(self.call('GET', '/api/papers?year=bad')[0], 400)

    def test_admin_write_survives_independent_workspace_and_invalidates_etag(self):
        before = self.call('GET', '/api/papers')[1]['ETag']
        member = {'slug': 'new-member', 'name': '新成员', 'openalexAuthorId': 'A222222'}
        self.assertEqual(self.call('POST', '/api/admin/researchers', payload=member)[0], 401)
        result = self.call('POST', '/api/admin/researchers', payload=member, admin=True)
        self.assertEqual(result[0], 201)
        self.assertEqual(result[1]['Cache-Control'], 'no-store')
        self.assertEqual(len(self.call('GET', '/api/researchers')[2]['researchers']), 2)
        self.assertNotEqual(self.call('GET', '/api/papers')[1]['ETag'], before)
        self.assertEqual(self.call('GET', '/api/papers?researcher=new-member')[2]['total'], 0)

    def test_conflicting_snapshots_never_overwrite_a_winner(self):
        with self.assertRaises(WriteConflict):
            with paper_workspace(self.store, self.settings, write=True) as first:
                create_researcher(first, {'slug': 'loser', 'name': '甲', 'openalexAuthorId': 'A222'})
                with paper_workspace(self.store, self.settings, write=True) as second:
                    create_researcher(second, {'slug': 'winner', 'name': '乙', 'openalexAuthorId': 'A333'})
        with paper_workspace(self.store, self.settings) as read:
            slugs = [item['slug'] for item in list_researchers(read)]
        self.assertIn('winner', slugs)
        self.assertNotIn('loser', slugs)

    def test_upstream_failure_preserves_snapshot_and_records_sanitized_status(self):
        with paper_workspace(self.store, self.settings, write=True):
            pass
        before = dict(self.store.objects)
        with patch('app.sync_service.fetch_author_works', side_effect=RuntimeError('api_key=SECRET')):
            with self.assertRaises(RuntimeError):
                sync_cloud(self.store, self.settings)
        for key, value in before.items():
            self.assertEqual(self.store.objects[key], value)
        self.assertEqual(latest_run(self.store)['status'], 'failed')
        self.assertNotIn(b'SECRET', b''.join(self.store.objects.values()))

    def test_scheduled_sync_publishes_once_and_repeated_timer_skips(self):
        from test_backend import _fake_work
        self.settings = replace(self.settings, sync_minimum_ratio=0.1)
        papers = self.call('GET', '/api/papers')[2]['papers'][:20]
        works = [_fake_work(paper, index) for index, paper in enumerate(papers)]
        with patch('app.sync_service.fetch_author_works', return_value=works) as fetch:
            first = scheduled_job(self.store, self.settings)
            second = scheduled_job(self.store, self.settings)
        self.assertEqual(first['sync']['status'], 'success')
        self.assertEqual(second['sync']['status'], 'skipped')
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(first['sync']['snapshotVersion'], self.call('GET', '/api/papers/version')[2]['version'])
        self.assertEqual(len(self.store.list('papers/snapshots/')), 1)

    def test_corrupt_snapshot_fails_instead_of_silently_reseeding(self):
        from app.cloud_papers import snapshot_key
        self.store.create(snapshot_key(1), b'corrupt')
        code, _, _ = self.call('GET', '/api/papers')
        self.assertGreaterEqual(code, 500)
        self.assertEqual(len(self.store.list('papers/snapshots/')), 1)

    def test_analytics_concurrency_deduplicates_without_lost_visitors(self):
        now = datetime(2026, 9, 6, 4, tzinfo=timezone.utc)
        def visit(index):
            return record_cloud_pageview(self.store, self.settings, path='/',
                                         client_ip=f'192.0.2.{index % 16}', user_agent='Browser', now=now)
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(visit, range(64)))
        self.assertEqual(sum(item['counted'] for item in results), 16)
        summary = get_cloud_summary(self.store, self.settings, now=now)
        self.assertEqual(summary['todayViews'], 16)
        self.assertEqual(summary['todayVisitors'], 16)
        self.assertEqual(summary['totalViews'], 116)
        self.assertNotIn('192.0.2.', ''.join(self.store.objects))

    def test_rollup_midnight_idempotency_and_retention(self):
        first = datetime(2026, 8, 1, 4, tzinfo=timezone.utc)
        record_cloud_pageview(self.store, self.settings, path='/', client_ip='one', user_agent='Browser', now=first)
        first_roll = rollup_analytics(self.store, self.settings, now=first + timedelta(days=1))
        self.assertEqual(first_roll['totalViews'], 101)
        self.assertEqual(rollup_analytics(self.store, self.settings, now=first + timedelta(days=1))['totalViews'], 101)
        last = first + timedelta(days=36)
        record_cloud_pageview(self.store, self.settings, path='/team', client_ip='two', user_agent='Browser', now=last)
        self.assertEqual(rollup_analytics(self.store, self.settings, now=last)['removedEvents'], 1)
        summary = get_cloud_summary(self.store, self.settings, now=last)
        self.assertEqual(summary['totalViews'], 102)
        self.assertEqual(summary['todayViews'], 1)
        midnight = datetime(2026, 9, 6, 16, 5, tzinfo=timezone.utc)
        self.assertEqual(rollup_analytics(self.store, self.settings, now=midnight)['through'], '2026-09-05')

    def test_analytics_origin_validation_and_clock_independent_etag(self):
        self.assertEqual(self.call('POST', '/api/analytics/pageview', payload={'path': '/'},
                                   headers={'origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.call('POST', '/api/analytics/pageview', payload={'path': '/admin'})[0], 400)
        self.assertEqual(self.call('POST', '/api/analytics/pageview', payload={'path': '/'})[0], 204)
        etag = self.call('GET', '/api/analytics/summary')[1]['ETag']
        self.assertEqual(self.call('GET', '/api/analytics/summary', headers={'if-none-match': etag})[0], 304)

    def test_budget_covers_retries_without_waiting_past_deadline(self):
        with sync_budget(0):
            with self.assertRaises(SyncDeadlineExceeded):
                remaining_timeout(60)
        with sync_budget(10), patch('app.budget.time.sleep') as sleep:
            with self.assertRaises(SyncDeadlineExceeded):
                retry_sleep(60)
            sleep.assert_not_called()

    def test_missing_secret_fails_closed(self):
        self.settings = replace(self.settings, sync_token=None, analytics_hmac_secret=None)
        self.assertEqual(self.call('POST', '/api/admin/sync')[0], 503)
        self.assertEqual(self.call('POST', '/api/analytics/pageview', payload={'path': '/'})[0], 503)


if __name__ == '__main__':
    unittest.main()
