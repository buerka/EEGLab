from __future__ import annotations

import json
import random
import urllib.error
import urllib.parse
import urllib.request

from .budget import remaining_timeout, retry_sleep


OPENALEX_BASE_URL = 'https://api.openalex.org/works'
SELECT_FIELDS = (
    'id,title,publication_year,publication_date,type,doi,authorships,'
    'primary_location,topics,cited_by_count,updated_date'
)


class OpenAlexError(RuntimeError):
    pass


def fetch_author_works(
    author_id: str,
    api_key: str | None,
    *,
    timeout: int = 60,
    max_attempts: int = 4,
) -> list[dict]:
    """使用 cursor 获取一名 OpenAlex 作者的全部论文。"""
    cursor = '*'
    works: list[dict] = []
    seen_cursors: set[str] = set()
    while cursor:
        remaining_timeout(timeout)
        if cursor in seen_cursors or len(seen_cursors) >= 100:
            raise OpenAlexError('OpenAlex 分页未前进或超过 100 页')
        seen_cursors.add(cursor)
        params = {
            'filter': f'authorships.author.id:{author_id}',
            'per_page': 100,
            'cursor': cursor,
            'sort': 'publication_date:desc',
            'select': SELECT_FIELDS,
        }
        if api_key:
            params['api_key'] = api_key
        payload = _request_json(
            f'{OPENALEX_BASE_URL}?{urllib.parse.urlencode(params)}',
            timeout=timeout,
            max_attempts=max_attempts,
        )
        works.extend(payload.get('results') or [])
        cursor = (payload.get('meta') or {}).get('next_cursor')
    return works


def _request_json(url: str, *, timeout: int, max_attempts: int) -> dict:
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        request = urllib.request.Request(
            url,
            headers={
                'Accept': 'application/json',
                'User-Agent': 'Jinniuhu-BCI-Lab-Publications/2.0',
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=remaining_timeout(timeout)) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (429, 500, 502, 503, 504) or attempt == max_attempts - 1:
                detail = exc.read().decode('utf-8', errors='replace')
                raise OpenAlexError(f'OpenAlex HTTP {exc.code}: {detail[:500]}') from exc
            retry_after = exc.headers.get('Retry-After')
            delay = min(60.0, float(retry_after)) if retry_after else _backoff(attempt)
            retry_sleep(delay)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == max_attempts - 1:
                raise OpenAlexError(f'OpenAlex request failed: {exc}') from exc
            retry_sleep(_backoff(attempt))
    raise OpenAlexError(f'OpenAlex request failed: {last_error}')


def _backoff(attempt: int) -> float:
    return min(30.0, (2 ** attempt) + random.uniform(0, 0.25))
