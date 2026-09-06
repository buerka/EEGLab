from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone

from .budget import sync_budget
from .cloud_analytics import rollup_analytics
from .cloud_papers import paper_workspace
from .cos_store import create_json, get_json
from .database import connect, get_metadata, set_metadata, utc_now
from .repository import get_sync_status
from .sync_service import sync_all_researchers


def latest_run(store):
    keys = store.list('papers/runs/', limit=1)
    return get_json(store, keys[0]) if keys else None


def sync_cloud(store, settings, *, seconds=70, daily=False):
    started = utc_now()
    run_key = f'papers/runs/{9999999999999 - int(time.time() * 1000):013d}-{uuid.uuid4().hex}.json'
    today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    try:
        with paper_workspace(store, settings, write=True) as local:
            if daily:
                with connect(local.database_path) as connection:
                    if get_metadata(connection, 'last_daily_sync') == today:
                        # No publication is needed; exit the context without writing.
                        raise AlreadySynced()
            with sync_budget(seconds):
                result = sync_all_researchers(local)
            with connect(local.database_path) as connection:
                if daily:
                    set_metadata(connection, 'last_daily_sync', today)
                # Administrative changes and syncs must invalidate the same cache.
                version = uuid.uuid4().hex
                set_metadata(connection, 'snapshot_version', version)
                connection.execute('UPDATE sync_runs SET snapshot_version=? WHERE id=?',
                                   (version, result.run_id))
                result.snapshot_version = version
            status = get_sync_status(local)
        create_json(store, run_key, status)
        return result.as_dict()
    except AlreadySynced:
        return {'status': 'skipped', 'reason': 'already_synced_today'}
    except Exception as exc:
        # Upstream exceptions may contain credentials in URLs; do not persist them.
        create_json(store, run_key, {'status': 'failed', 'startedAt': started,
                                     'finishedAt': utc_now(), 'error': type(exc).__name__})
        raise


class AlreadySynced(Exception):
    pass


def scheduled_job(store, settings):
    with sync_budget(250):
        # Rollups still run when an upstream publication source is unavailable.
        analytics = rollup_analytics(store, settings)
        sync = sync_cloud(store, settings, seconds=200, daily=True)
    return {'analytics': analytics, 'sync': sync}
