from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


SERPAPI_URL = 'https://serpapi.com/search.json'


class ScholarError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScholarProfile:
    articles: list[dict]
    total_citations: int | None
    h_index: int | None
    i10_index: int | None


def fetch_author_profile(
    scholar_id: str,
    api_key: str,
    *,
    timeout: int = 60,
    max_attempts: int = 4,
) -> ScholarProfile:
    """通过 SerpAPI 分页获取 Scholar 作者文章和作者级指标。"""
    articles: list[dict] = []
    metrics: tuple[int | None, int | None, int | None] = (None, None, None)
    start = 0
    page_size = 100
    seen_page_signatures: set[tuple[str, ...]] = set()
    seen_citation_ids: set[str] = set()
    for page_number in range(20):
        params = {
            'engine': 'google_scholar_author',
            'author_id': scholar_id,
            'api_key': api_key,
            'hl': 'en',
            'sort': 'pubdate',
            'num': page_size,
            'start': start,
        }
        payload = _request_json(
            f'{SERPAPI_URL}?{urllib.parse.urlencode(params)}',
            timeout=timeout,
            max_attempts=max_attempts,
        )
        if payload.get('error'):
            raise ScholarError(f'SerpAPI: {payload["error"]}')
        if page_number == 0:
            metrics = _parse_metrics(payload.get('cited_by') or {})
        raw_page = payload.get('articles') or []
        page = [_normalize_article(item) for item in raw_page]
        valid_page = [item for item in page if item['citation_id'] and item['title']]
        signature = tuple(item['citation_id'] for item in valid_page)
        if signature and signature in seen_page_signatures:
            raise ScholarError(
                f'Scholar 分页未前进（start={start}），已停止以避免重复消耗配额'
            )
        seen_page_signatures.add(signature)
        for item in valid_page:
            if item['citation_id'] not in seen_citation_ids:
                articles.append(item)
                seen_citation_ids.add(item['citation_id'])
        pagination = payload.get('serpapi_pagination') or {}
        next_url = pagination.get('next')
        if not next_url or not raw_page:
            break
        next_start = _pagination_start(next_url)
        if next_start is None:
            next_start = start + len(raw_page)
        if next_start <= start:
            raise ScholarError(
                f'Scholar 返回了无效的下一页游标 {next_start}（当前 {start}）'
            )
        start = next_start
    else:
        raise ScholarError('Scholar 分页超过 20 页，已停止以避免失控消耗配额')
    return ScholarProfile(articles, *metrics)


def _normalize_article(item: dict) -> dict:
    cited_by = item.get('cited_by') or {}
    try:
        year = int(item.get('year') or 0)
    except (TypeError, ValueError):
        year = 0
    return {
        'citation_id': str(item.get('citation_id') or '').strip(),
        'title': str(item.get('title') or '').strip(),
        'authors': str(item.get('authors') or '').strip(),
        'publication': str(item.get('publication') or '').strip(),
        'year': year,
        'cited_by_count': int(cited_by.get('value') or 0),
        'link': item.get('link'),
    }


def _parse_metrics(cited_by: dict) -> tuple[int | None, int | None, int | None]:
    table = cited_by.get('table') or []
    if not table:
        return None, None, None
    citations = h_index = i10_index = None
    for row in table:
        citations = citations if citations is not None else _metric_value(row.get('citations'))
        h_index = h_index if h_index is not None else _metric_value(
            row.get('h_index') or row.get('indice_h')
        )
        i10_index = i10_index if i10_index is not None else _metric_value(
            row.get('i10_index') or row.get('indice_i10')
        )
    return citations, h_index, i10_index


def _pagination_start(url: str) -> int | None:
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    value = (query.get('start') or query.get('cstart') or [None])[0]
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _metric_value(value: object) -> int | None:
    if isinstance(value, dict):
        value = value.get('all')
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


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
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (429, 500, 502, 503, 504) or attempt == max_attempts - 1:
                detail = exc.read().decode('utf-8', errors='replace')
                raise ScholarError(f'SerpAPI HTTP {exc.code}: {detail[:500]}') from exc
            retry_after = exc.headers.get('Retry-After')
            delay = min(60.0, float(retry_after)) if retry_after else _backoff(attempt)
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == max_attempts - 1:
                raise ScholarError(f'SerpAPI request failed: {exc}') from exc
            time.sleep(_backoff(attempt))
    raise ScholarError(f'SerpAPI request failed: {last_error}')


def _backoff(attempt: int) -> float:
    return min(30.0, (2 ** attempt) + random.uniform(0, 0.25))
