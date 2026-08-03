from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

from app.config import BACKEND_ROOT, Settings
from app.database import connect, get_metadata, initialize
from app.repository import create_researcher, get_publications, list_scholar_candidates
from app.sync_service import sync_all_researchers
from app.scholar import ScholarProfile
from app.review_service import apply_scholar_review_rules


class BackendTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings = Settings(
            database_path=Path(self.temp_dir.name) / 'papers.db',
            researchers_seed_path=BACKEND_ROOT / 'data' / 'researchers.toml',
            papers_seed_path=BACKEND_ROOT / 'data' / 'papers.toml',
            openalex_api_key='test-key',
            sync_token='test-token',
            allowed_origins=('http://localhost:4321',),
            cache_control='public, max-age=0, s-maxage=60',
            sync_interval_seconds=86400,
            sync_minimum_ratio=0.1,
        )
        initialize(self.settings)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_seed_preserves_136_papers_and_manual_fields(self) -> None:
        data = get_publications(self.settings, {'limit': 500})
        self.assertEqual(data['total'], 136)
        self.assertEqual(
            data['typeCounts']['journal'] + data['typeCounts']['conference'],
            data['total'],
        )
        self.assertEqual(len(data['researchers']), 1)
        self.assertEqual(data['researchers'][0]['slug'], 'ying-yan')
        self.assertEqual(sum(1 for paper in data['papers'] if paper['representative']), 3)
        self.assertTrue(any(paper['impactFactor'] for paper in data['papers']))
        self.assertTrue(any(paper['isTop'] for paper in data['papers']))

    def test_api_etag_filters_and_multi_researcher_contract(self) -> None:
        from app import main

        original_settings = main.settings
        main.settings = self.settings
        try:
            with TestClient(main.app) as client:
                response = client.get('/api/papers')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['total'], 136)
                self.assertIn('etag', response.headers)
                unchanged = client.get(
                    '/api/papers', headers={'If-None-Match': response.headers['etag']}
                )
                self.assertEqual(unchanged.status_code, 304)

                created = client.post(
                    '/api/admin/researchers',
                    headers={'Authorization': 'Bearer test-token'},
                    json={
                        'slug': 'second-member',
                        'name': '第二位成员',
                        'nameEn': 'Second Member',
                        'openalexAuthorId': 'A222222',
                    },
                )
                self.assertEqual(created.status_code, 201)
                researchers = client.get('/api/researchers').json()['researchers']
                self.assertEqual([item['slug'] for item in researchers], ['ying-yan', 'second-member'])
                filtered = client.get('/api/papers?researcher=second-member').json()
                self.assertEqual(filtered['total'], 0)
        finally:
            main.settings = original_settings

    def test_sync_is_transactional_keeps_missing_and_links_shared_papers(self) -> None:
        create_researcher(self.settings, {
            'slug': 'second-member',
            'name': '第二位成员',
            'openalexAuthorId': 'A222222',
        })
        before = get_publications(self.settings, {'limit': 500})
        works = [_fake_work(paper, index) for index, paper in enumerate(before['papers'][:14])]

        def fake_fetch(author_id: str, _: str | None) -> list[dict]:
            if author_id == 'A222222':
                return [works[0]]
            return works

        with patch('app.sync_service.fetch_author_works', side_effect=fake_fetch):
            result = sync_all_researchers(self.settings)

        self.assertEqual(result.status, 'success')
        after = get_publications(self.settings, {'limit': 500})
        self.assertEqual(after['total'], 136, '单次上游缺失不能删除旧论文')
        shared = next(paper for paper in after['papers'] if paper['doi'] == works[0]['doi'])
        self.assertEqual(
            {item['slug'] for item in shared['researchers']},
            {'ying-yan', 'second-member'},
        )
        self.assertEqual(sum(1 for paper in after['papers'] if paper['representative']), 3)

        with connect(self.settings.database_path) as connection:
            version_before_failure = get_metadata(connection, 'snapshot_version')
        with patch('app.sync_service.fetch_author_works', return_value=[]):
            with self.assertRaises(RuntimeError):
                sync_all_researchers(self.settings)
        with connect(self.settings.database_path) as connection:
            self.assertEqual(get_metadata(connection, 'snapshot_version'), version_before_failure)

    def test_scholar_reconciles_without_publishing_unmatched_candidates(self) -> None:
        scholar_settings = replace(self.settings, serpapi_api_key='serp-secret')
        before = get_publications(scholar_settings, {'limit': 500})
        works = [_fake_work(paper, index) for index, paper in enumerate(before['papers'][:14])]
        matched_paper = before['papers'][0]
        profile = ScholarProfile(
            articles=[
                {
                    'citation_id': 'lkDrRmoAAAAJ:matched',
                    'title': matched_paper['title'],
                    'authors': matched_paper['authors'],
                    'publication': matched_paper['journal'],
                    'year': matched_paper['year'],
                    'cited_by_count': 88,
                    'link': 'https://scholar.google.test/matched',
                },
                {
                    'citation_id': 'lkDrRmoAAAAJ:unmatched',
                    'title': 'A definitely unrelated Scholar record',
                    'authors': 'Someone Else',
                    'publication': 'Unknown',
                    'year': 2026,
                    'cited_by_count': 1,
                    'link': 'https://scholar.google.test/unmatched',
                },
            ],
            total_citations=999,
            h_index=20,
            i10_index=31,
        )
        with (
            patch('app.sync_service.fetch_author_works', return_value=works),
            patch('app.sync_service.fetch_author_profile', return_value=profile),
        ):
            result = sync_all_researchers(scholar_settings)

        self.assertEqual(result.scholar_matched_count, 1)
        self.assertEqual(result.scholar_candidate_count, 1)
        after = get_publications(scholar_settings, {'limit': 500})
        self.assertEqual(after['total'], 136)
        paper = next(item for item in after['papers'] if item['doi'] == matched_paper['doi'])
        self.assertEqual(paper['sourceStatus'], 'confirmed')
        self.assertEqual(paper['citationSources']['googleScholar'], 88)
        self.assertEqual(after['researchers'][0]['scholarMetrics']['hIndex'], 20)
        with connect(scholar_settings.database_path) as connection:
            candidate_count = connection.execute(
                'SELECT COUNT(*) FROM scholar_candidates WHERE missing_since IS NULL'
            ).fetchone()[0]
        self.assertEqual(candidate_count, 1)

    def test_review_rules_are_idempotent_and_materialize_scholar_only_papers(self) -> None:
        with connect(self.settings.database_path) as connection:
            researcher_id = connection.execute(
                "SELECT id FROM researchers WHERE slug='ying-yan'"
            ).fetchone()['id']
            now = '2026-08-02T00:00:00Z'
            connection.execute(
                """
                INSERT INTO scholar_candidates (
                    researcher_id, citation_id, normalized_title, title, authors,
                    publication, publication_year, cited_by_count, match_status,
                    match_score, last_seen_at
                ) VALUES (?, 'test:accept', 'reviewedpaper', 'Reviewed Paper',
                          'Y Yan, J Cai', 'Test Journal', 2026, 5,
                          'unmatched', 0.2, ?)
                """,
                (researcher_id, now),
            )
            connection.execute(
                """
                INSERT INTO scholar_review_rules (
                    researcher_id, citation_id, decision, notes, reviewed_at
                ) VALUES (?, 'test:accept', 'accept', 'confirmed', ?)
                """,
                (researcher_id, now),
            )

        first = apply_scholar_review_rules(self.settings)
        second = apply_scholar_review_rules(self.settings)
        self.assertEqual(first, {'applied': 1, 'accepted': 1, 'excluded': 0})
        self.assertEqual(second, {'applied': 0, 'accepted': 0, 'excluded': 0})
        self.assertEqual(list_scholar_candidates(self.settings), [])
        data = get_publications(self.settings, {'limit': 500})
        reviewed = next(item for item in data['papers'] if item['title'] == 'Reviewed Paper')
        self.assertEqual(reviewed['sourceStatus'], 'scholar_only')
        self.assertEqual(reviewed['citationSources']['googleScholar'], 5)
        self.assertIsNone(reviewed['citationSources']['openalex'])


def _fake_work(paper: dict, index: int) -> dict:
    researchers = paper['researchers']
    author_id = 'A5101638873'
    return {
        'id': f'https://openalex.org/WTEST{index}',
        'doi': paper['doi'],
        'title': paper['title'],
        'publication_year': paper['year'],
        'publication_date': paper.get('publicationDate') or f'{paper["year"]}-01-01',
        'type': 'article',
        'cited_by_count': 10 + index,
        'updated_date': '2026-08-02T00:00:00Z',
        'authorships': [{
            'author': {'id': f'https://openalex.org/{author_id}', 'display_name': 'Ying Yan'},
            'is_corresponding': True,
        }],
        'primary_location': {
            'source': {'display_name': paper['journal'], 'type': 'journal'},
        },
        'topics': [{'display_name': 'Electroencephalography'}],
    }


if __name__ == '__main__':
    unittest.main()
