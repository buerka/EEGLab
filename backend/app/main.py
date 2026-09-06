from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .analytics import (
    get_analytics_summary,
    initialize_analytics,
    make_analytics_etag,
    normalize_public_path,
    record_pageview,
)
from .config import get_settings
from .database import initialize
from .repository import (
    create_researcher,
    get_publications,
    get_sync_status,
    list_scholar_candidates,
    list_researchers,
    make_etag,
)
from .sync_service import sync_all_researchers


settings = get_settings()
sync_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(_: Starlette):
    await run_in_threadpool(initialize, settings)
    await run_in_threadpool(initialize_analytics, settings)
    yield


async def health(_: Request) -> JSONResponse:
    return JSONResponse({'status': 'ok'})


async def researchers(_: Request) -> JSONResponse:
    data = await run_in_threadpool(list_researchers, settings)
    return _public_json({'researchers': data})


async def papers(request: Request) -> Response:
    researcher_values = request.query_params.getlist('researcher')
    researcher_slugs = {
        slug.strip() for value in researcher_values for slug in value.split(',') if slug.strip()
    }
    representative_value = request.query_params.get('representative')
    filters = {
        'researchers': researcher_slugs,
        'tag': request.query_params.get('tag'),
        'field': request.query_params.get('field'),
        'year': _optional_int(request.query_params.get('year')),
        'representative': (
            representative_value.lower() == 'true' if representative_value else None
        ),
        'query': request.query_params.get('q'),
        'limit': _optional_int(request.query_params.get('limit')) or 500,
        'offset': _optional_int(request.query_params.get('offset')) or 0,
    }
    data = await run_in_threadpool(get_publications, settings, filters)
    etag = make_etag(data['version'], request.url.query)
    if request.headers.get('if-none-match') == etag:
        return Response(status_code=304, headers={
            'ETag': etag, 'Cache-Control': settings.cache_control,
        })
    return _public_json(data, headers={'ETag': etag})


async def papers_version(_: Request) -> JSONResponse:
    status = await run_in_threadpool(get_sync_status, settings)
    return _public_json({
        'version': status.get('snapshotVersion'),
        'updatedAt': status.get('lastSyncAt'),
    })


async def sync_status(_: Request) -> JSONResponse:
    return _public_json(await run_in_threadpool(get_sync_status, settings))


async def analytics_pageview(request: Request) -> Response:
    if not _analytics_origin_allowed(request):
        return JSONResponse(
            {'error': '不允许的请求来源'},
            status_code=403,
            headers={'Cache-Control': 'no-store'},
        )
    content_length = _optional_int(request.headers.get('content-length')) or 0
    if content_length > 1024:
        return JSONResponse(
            {'error': '请求体过大'},
            status_code=413,
            headers={'Cache-Control': 'no-store'},
        )
    try:
        payload = await request.json()
        path = normalize_public_path(payload.get('path') if isinstance(payload, dict) else None)
        if path is None:
            raise ValueError('无效的页面路径')
    except (ValueError, json.JSONDecodeError):
        return JSONResponse(
            {'error': '无效的访问记录'},
            status_code=400,
            headers={'Cache-Control': 'no-store'},
        )

    await run_in_threadpool(
        record_pageview,
        settings,
        path=path,
        client_ip=_analytics_client_ip(request),
        user_agent=request.headers.get('user-agent', ''),
    )
    return Response(status_code=204, headers={'Cache-Control': 'no-store'})


async def analytics_summary(request: Request) -> Response:
    data = await run_in_threadpool(get_analytics_summary, settings)
    etag = make_analytics_etag(data)
    headers = {'ETag': etag, 'Cache-Control': settings.analytics_cache_control}
    if request.headers.get('if-none-match') == etag:
        return Response(status_code=304, headers=headers)
    return JSONResponse(data, headers=headers)


async def trigger_sync(request: Request) -> JSONResponse:
    unauthorized = _require_admin(request)
    if unauthorized:
        return unauthorized
    if sync_lock.locked():
        return JSONResponse({'error': '同步任务正在运行'}, status_code=409)
    async with sync_lock:
        try:
            result = await run_in_threadpool(sync_all_researchers, settings)
            return JSONResponse(result.as_dict())
        except Exception as exc:
            return JSONResponse({'error': str(exc)}, status_code=502)


async def add_researcher(request: Request) -> JSONResponse:
    unauthorized = _require_admin(request)
    if unauthorized:
        return unauthorized
    try:
        payload = await request.json()
        researcher = await run_in_threadpool(create_researcher, settings, payload)
        return JSONResponse(researcher, status_code=201)
    except (ValueError, json.JSONDecodeError) as exc:
        return JSONResponse({'error': str(exc)}, status_code=400)
    except sqlite3.IntegrityError as exc:
        return JSONResponse({'error': f'研究者已存在或标识冲突: {exc}'}, status_code=409)


async def scholar_candidates(request: Request) -> JSONResponse:
    unauthorized = _require_admin(request)
    if unauthorized:
        return unauthorized
    data = await run_in_threadpool(list_scholar_candidates, settings)
    return JSONResponse({'candidates': data})


def _require_admin(request: Request) -> JSONResponse | None:
    if not settings.sync_token:
        return JSONResponse({'error': '服务器未配置 PAPERS_SYNC_TOKEN'}, status_code=503)
    authorization = request.headers.get('authorization', '')
    token = authorization[7:] if authorization.startswith('Bearer ') else ''
    if token != settings.sync_token:
        return JSONResponse({'error': 'Unauthorized'}, status_code=401)
    return None


def _analytics_origin_allowed(request: Request) -> bool:
    origin = (request.headers.get('origin') or '').rstrip('/')
    if not origin:
        return request.headers.get('sec-fetch-site', '') in ('', 'same-origin', 'same-site')
    request_origin = f'{request.url.scheme}://{request.url.netloc}'.rstrip('/')
    allowed = {value.rstrip('/') for value in settings.allowed_origins}
    return origin == request_origin or origin in allowed


def _analytics_client_ip(request: Request) -> str:
    cloudflare_ip = request.headers.get('cf-connecting-ip')
    if cloudflare_ip:
        return cloudflare_ip.strip()
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        return forwarded.split(',', 1)[0].strip()
    real_ip = request.headers.get('x-real-ip')
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else 'unknown'


def _public_json(payload: dict, *, headers: dict | None = None) -> JSONResponse:
    response_headers = {'Cache-Control': settings.cache_control, **(headers or {})}
    return JSONResponse(payload, headers=response_headers)


def _optional_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


routes = [
    Route('/health', health),
    Route('/api/researchers', researchers),
    Route('/api/papers', papers),
    Route('/api/papers/version', papers_version),
    Route('/api/sync/status', sync_status),
    Route('/api/analytics/pageview', analytics_pageview, methods=['POST']),
    Route('/api/analytics/summary', analytics_summary),
    Route('/api/admin/sync', trigger_sync, methods=['POST']),
    Route('/api/admin/researchers', add_researcher, methods=['POST']),
    Route('/api/admin/scholar-candidates', scholar_candidates),
]

app = Starlette(routes=routes, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_methods=['GET', 'POST'],
    allow_headers=['Authorization', 'Content-Type', 'If-None-Match'],
    expose_headers=['ETag'],
)
