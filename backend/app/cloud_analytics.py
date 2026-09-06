"""Low-volume site analytics: immutable deduplicated events + daily rollups.

Only day-scoped HMACs are persisted, never raw IP/UA. Counting uses object keys,
so independent invocations do not read/modify/write a shared counter.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from .analytics import _as_utc, _local_day, _visitor_hash, _iso_utc, is_probable_bot, normalize_public_path
from .cos_store import StorageError, WriteConflict, get_json, create_json


MAX_PENDING_EVENTS = 50000


def _initial(store, settings, moment):
    initial = get_json(store, 'analytics/initial.json')
    if initial is None:
        initial = {'trackingSince': _local_day(moment),
                   'totalViews': settings.analytics_initial_total}
        try:
            create_json(store, 'analytics/initial.json', initial)
        except WriteConflict:
            initial = get_json(store, 'analytics/initial.json')
    if not isinstance(initial, dict):
        raise StorageError('访问统计初始化失败')
    return initial


def _latest(store):
    keys = store.list('analytics/rollups/', limit=1)
    return get_json(store, keys[0]) if keys else None


def _pending(store, through=''):
    marker = f'analytics/events/{through}~' if through else ''
    keys = store.list('analytics/events/', marker=marker, limit=MAX_PENDING_EVENTS + 1)
    if len(keys) > MAX_PENDING_EVENTS:
        raise StorageError('待汇总统计超过 50000 条，请先执行 SCF 汇总任务')
    return keys


def record_cloud_pageview(store, settings, *, path, client_ip, user_agent, now=None):
    path = normalize_public_path(path)
    if path is None:
        raise ValueError('无效的页面路径')
    if is_probable_bot(user_agent):
        return {'counted': False, 'reason': 'bot'}
    moment = _as_utc(now)
    _initial(store, settings, moment)
    day = _local_day(moment)
    visitor = _visitor_hash(settings, day, client_ip, user_agent)
    page = hashlib.sha256(path.encode()).hexdigest()[:16]
    # Fixed time windows are deterministic across instances, including retries.
    bucket = int(moment.timestamp()) // settings.analytics_dedupe_seconds
    key = f'analytics/events/{day}/{visitor}/{page}-{bucket}'
    try:
        store.create(key, b'')
        return {'counted': True}
    except WriteConflict:
        return {'counted': False, 'reason': 'deduplicated'}


def get_cloud_summary(store, settings, *, now=None):
    moment = _as_utc(now)
    initial = _initial(store, settings, moment)
    latest = _latest(store)
    keys = _pending(store, latest['through'] if latest else '')
    today = _local_day(moment)
    today_keys = [key for key in keys if key.split('/')[2] == today]
    return {
        'totalViews': (latest['totalViews'] if latest else initial['totalViews']) + len(keys),
        'todayViews': len(today_keys),
        'todayVisitors': len({key.split('/')[3] for key in today_keys}),
        'trackingSince': initial['trackingSince'],
        'updatedAt': _iso_utc(moment),
    }


def rollup_analytics(store, settings, *, now=None):
    moment = _as_utc(now)
    initial = _initial(store, settings, moment)
    # Finalize only after a 10 minute midnight grace period (SCF max 300s).
    cutoff = (datetime.fromisoformat(_local_day(moment)) - timedelta(days=1)).date()
    from .analytics import CHINA_TIMEZONE
    local = moment.astimezone(CHINA_TIMEZONE)
    if local.hour == 0 and local.minute < 10:
        cutoff -= timedelta(days=1)
    through = cutoff.isoformat()
    latest = _latest(store)
    if not latest or latest['through'] < through:
        keys = _pending(store, latest['through'] if latest else '')
        historical = [key for key in keys if key.split('/')[2] <= through]
        days = {}
        for key in historical:
            day, visitor = key.split('/')[2:4]
            item = days.setdefault(day, {'views': 0, 'visitors': set()})
            item['views'] += 1
            item['visitors'].add(visitor)
        summary = {
            'through': through,
            'totalViews': (latest['totalViews'] if latest else initial['totalViews']) + len(historical),
            'days': {day: {'views': value['views'], 'visitors': len(value['visitors'])}
                     for day, value in days.items()},
            'trackingSince': initial['trackingSince'],
        }
        key = f'analytics/rollups/{99999999 - int(through.replace("-", "")):08d}.json'
        try:
            create_json(store, key, summary)
        except WriteConflict:
            existing = get_json(store, key)
            if existing != summary:
                raise StorageError('统计汇总并发冲突，保留原始记录以便重试')
        latest = summary
    # Delete only records included in a successful rollup, beyond 32 days.
    expiry = (local.date() - timedelta(days=32)).isoformat()
    old_keys = store.list('analytics/events/', limit=10000)
    expired = [key for key in old_keys
               if key.split('/')[2] < expiry and key.split('/')[2] <= latest['through']]
    store.delete(expired)
    return {'through': latest['through'], 'totalViews': latest['totalViews'],
            'removedEvents': len(expired)}
