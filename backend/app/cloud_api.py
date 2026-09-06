"""Makers API transport, independent of a persistent ASGI server or lifespan."""
from __future__ import annotations

import hmac
import json
import sqlite3
import uuid
from urllib.parse import parse_qs, urlsplit

from .analytics import make_analytics_etag, normalize_public_path
from .budget import sync_budget, SyncDeadlineExceeded
from .cloud_analytics import record_cloud_pageview, get_cloud_summary
from .cloud_papers import paper_workspace
from .cloud_runtime import sync_cloud, latest_run
from .config import get_settings
from .cos_store import CosStore, StorageError, WriteConflict
from .database import connect, set_metadata
from .repository import (get_publications, list_researchers, get_sync_status,
                         list_scholar_candidates, create_researcher, make_etag)


def dispatch(method, target, headers=None, body=b'', *, store=None, settings=None):
    headers = {key.lower(): value for key, value in (headers or {}).items()}
    settings = settings or get_settings()
    url = urlsplit(target)
    path = url.path.rstrip('/') or '/'
    # Handler runtimes may retain or strip the /api file-route prefix.
    if path.startswith('/api/'):
        path = path[4:]
    query = parse_qs(url.query)
    common = {'Content-Type': 'application/json; charset=utf-8',
              'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
    origin = headers.get('origin', '').rstrip('/')
    allowed = {item.rstrip('/') for item in settings.allowed_origins}
    host = headers.get('host', '')
    same_origin = origin == f'https://{host}' and bool(host)
    if origin and (origin in allowed or same_origin):
        common.update({'Access-Control-Allow-Origin': origin, 'Vary': 'Origin',
                       'Access-Control-Expose-Headers': 'ETag'})

    def response(status, payload=None, **extra):
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else b''
        return status, {**common, **extra}, data

    if method == 'OPTIONS':
        if origin and not (origin in allowed or same_origin):
            return response(403, {'error': '不允许的请求来源'})
        return response(204, **{'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                               'Access-Control-Allow-Headers': 'Authorization, Content-Type, If-None-Match'})
    if path == '/health' and method == 'GET':
        return response(200, {'status': 'ok', 'runtime': 'makers-python', 'storage': 'cos'})
    if path.startswith('/admin/'):
        if not settings.sync_token or len(settings.sync_token) < 32:
            return response(503, {'error': '请配置至少 32 字符的 PAPERS_SYNC_TOKEN'})
        if not hmac.compare_digest(headers.get('authorization', '').encode(),
                                   f'Bearer {settings.sync_token}'.encode()):
            return response(401, {'error': 'Unauthorized'})
    routes = {'/papers': 'GET', '/researchers': 'GET', '/papers/version': 'GET',
              '/sync/status': 'GET', '/analytics/summary': 'GET', '/analytics/pageview': 'POST',
              '/admin/sync': 'POST', '/admin/researchers': 'POST', '/admin/scholar-candidates': 'GET'}
    if path not in routes:
        return response(404, {'error': 'Not found'})
    if routes[path] != method:
        return response(405, {'error': 'Method not allowed'}, Allow=routes[path])
    if len(body) > (1024 if path == '/analytics/pageview' else 8192):
        return response(413, {'error': '请求体过大'})
    try:
        payload = json.loads(body) if body else {}
        if not isinstance(payload, dict):
            return response(400, {'error': 'JSON 请求体必须是对象'})
        with sync_budget(105):
            store = store if store is not None else CosStore()
            etag = None
            cache = settings.cache_control
            if path.startswith('/analytics/'):
                secret = settings.analytics_hmac_secret or settings.sync_token
                if not secret or len(secret) < 32:
                    return response(503, {'error': '请配置至少 32 字符的 ANALYTICS_HMAC_SECRET'})
                if path == '/analytics/pageview':
                    if origin and not (origin in allowed or same_origin):
                        return response(403, {'error': '不允许的请求来源'})
                    if headers.get('sec-fetch-site') == 'cross-site' and not origin:
                        return response(403, {'error': '不允许的请求来源'})
                    page = normalize_public_path(payload.get('path'))
                    if page is None:
                        return response(400, {'error': '无效的页面路径'})
                    record_cloud_pageview(store, settings, path=page,
                                          client_ip=headers.get('eo-connecting-ip') or
                                          headers.get('x-forwarded-for', '').split(',')[0].strip() or 'unknown',
                                          user_agent=headers.get('user-agent', ''))
                    return response(204)
                data = get_cloud_summary(store, settings)
                # The date/clock is not part of the version; unchanged counters yield 304.
                etag = make_analytics_etag({key: value for key, value in data.items() if key != 'updatedAt'})
                cache = settings.analytics_cache_control
            elif path == '/admin/sync':
                return response(200, sync_cloud(store, settings))
            else:
                write = path == '/admin/researchers'
                with paper_workspace(store, settings, write=write) as local:
                    if path == '/papers':
                        def integer(key, default=None):
                            return int(query[key][0]) if key in query else default
                        data = get_publications(local, {
                            'researchers': {slug.strip() for value in query.get('researcher', [])
                                            for slug in value.split(',') if slug.strip()},
                            'tag': query.get('tag', [None])[0], 'field': query.get('field', [None])[0],
                            'query': query.get('q', [''])[0], 'year': integer('year'),
                            'representative': query.get('representative', [''])[0].lower() == 'true',
                            'limit': integer('limit', 500), 'offset': integer('offset', 0),
                        })
                        etag = make_etag(data['version'], url.query)
                    elif path == '/researchers':
                        data = {'researchers': list_researchers(local)}
                    elif path == '/admin/researchers':
                        data = create_researcher(local, payload)
                        with connect(local.database_path) as connection:
                            set_metadata(connection, 'snapshot_version', uuid.uuid4().hex)
                    elif path == '/admin/scholar-candidates':
                        data = {'candidates': list_scholar_candidates(local)}
                    else:
                        data = get_sync_status(local)
                        if path == '/sync/status':
                            attempt = latest_run(store)
                            if attempt:
                                data['lastAttempt'] = attempt
                                data['status'] = attempt['status']
                                data['error'] = attempt.get('error')
                        else:
                            data = {'version': data.get('snapshotVersion'), 'updatedAt': data.get('lastSyncAt')}
            if path.startswith('/admin/'):
                cache = 'no-store'
            extra = {'Cache-Control': cache}
            if etag:
                extra['ETag'] = etag
                if headers.get('if-none-match') == etag:
                    return response(304, **extra)
            return response(201 if path == '/admin/researchers' else 200, data, **extra)
    except WriteConflict:
        return response(409, {'error': '其他任务已更新数据，请重试'})
    except (ValueError, TypeError, sqlite3.IntegrityError):
        return response(400, {'error': '无效参数或研究者标识重复'})
    except SyncDeadlineExceeded:
        return response(504, {'error': '同步超时，保留上次快照；完整同步请使用 SCF 定时任务'})
    except StorageError:
        return response(503, {'error': '持久化存储暂不可用，请检查 COS 配置'})
    except Exception:
        return response(502, {'error': '论文服务暂不可用，已保留上次完整快照'})
