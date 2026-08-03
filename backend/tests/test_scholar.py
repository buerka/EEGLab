from __future__ import annotations

import unittest
from unittest.mock import patch

from app.scholar import ScholarError, fetch_author_profile


class ScholarClientTestCase(unittest.TestCase):
    def test_fetches_pages_and_author_metrics(self) -> None:
        first = {
            'articles': [{
                'citation_id': 'abc:one', 'title': 'Paper One', 'authors': 'A, B',
                'publication': 'Journal', 'year': '2025',
                'cited_by': {'value': 17}, 'link': 'https://example.test/one',
            }],
            'cited_by': {'table': [{
                'citations': {'all': 123}, 'h_index': {'all': 8},
                'i10_index': {'all': 5},
            }]},
            'serpapi_pagination': {
                'next': 'https://serpapi.com/search.json?cstart=20&engine=google_scholar_author'
            },
        }
        second = {
            'articles': [{
                'citation_id': 'abc:two', 'title': 'Paper Two', 'year': 2024,
                'cited_by': {'value': 3},
            }],
            'serpapi_pagination': {},
        }
        with patch('app.scholar._request_json', side_effect=[first, second]) as request:
            profile = fetch_author_profile('abc', 'secret')
        self.assertEqual(len(profile.articles), 2)
        self.assertEqual(profile.total_citations, 123)
        self.assertEqual(profile.h_index, 8)
        self.assertEqual(profile.i10_index, 5)
        self.assertIn('start=20', request.call_args_list[1].args[0])
        self.assertNotIn('cstart=', request.call_args_list[1].args[0])

    def test_stops_immediately_when_serpapi_repeats_a_page(self) -> None:
        repeated = {
            'articles': [{'citation_id': 'abc:one', 'title': 'Paper One'}],
            'serpapi_pagination': {
                'next': 'https://serpapi.com/search.json?cstart=20&engine=google_scholar_author'
            },
        }
        with patch('app.scholar._request_json', side_effect=[repeated, repeated]) as request:
            with self.assertRaisesRegex(ScholarError, '分页未前进'):
                fetch_author_profile('abc', 'secret')
        self.assertEqual(request.call_count, 2)

    def test_surfaces_serpapi_error(self) -> None:
        with patch('app.scholar._request_json', return_value={'error': 'quota exhausted'}):
            with self.assertRaises(ScholarError):
                fetch_author_profile('abc', 'secret')


if __name__ == '__main__':
    unittest.main()
