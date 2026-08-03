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
