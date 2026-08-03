from __future__ import annotations

import unittest
from unittest.mock import patch

from app.openalex import fetch_author_works


class OpenAlexClientTestCase(unittest.TestCase):
    def test_uses_100_per_page_and_cursor_pagination(self) -> None:
        urls: list[str] = []
        responses = [
            {'results': [{'id': 'W1'}], 'meta': {'next_cursor': 'next'}},
            {'results': [{'id': 'W2'}], 'meta': {'next_cursor': None}},
        ]

        def fake_request(url: str, **_: object) -> dict:
            urls.append(url)
            return responses.pop(0)

        with patch('app.openalex._request_json', side_effect=fake_request):
            works = fetch_author_works('A123', 'key')
        self.assertEqual([work['id'] for work in works], ['W1', 'W2'])
        self.assertTrue(all('per_page=100' in url for url in urls))
        self.assertIn('cursor=%2A', urls[0])
        self.assertIn('cursor=next', urls[1])


if __name__ == '__main__':
    unittest.main()
