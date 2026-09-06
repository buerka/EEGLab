"""Immutable COS snapshots; SQLite is only an isolated request workspace."""
from __future__ import annotations

import gzip
import hashlib
import io
import sqlite3
import tempfile
from contextlib import contextmanager, closing
from dataclasses import replace
from pathlib import Path

from .cos_store import StorageError
from .database import initialize, connect, set_metadata


MAX_REVISION = 999999999999


def snapshot_key(revision: int) -> str:
    if not 0 < revision < MAX_REVISION:
        raise StorageError('论文快照版本超出范围')
    # COS lists keys in ascending order; the first key is the newest revision.
    return f'papers/snapshots/{MAX_REVISION - revision:012d}.sqlite.gz'


@contextmanager
def paper_workspace(store, settings, *, write: bool = False):
    keys = store.list('papers/snapshots/', limit=1)
    revision = MAX_REVISION - int(keys[0].rsplit('/', 1)[1].split('.')[0]) if keys else 0
    with tempfile.TemporaryDirectory(prefix='eeglab-papers-') as directory:
        path = Path(directory) / 'papers.db'
        local_settings = replace(settings, database_path=path)
        if keys:
            payload = store.get(keys[0])
            if payload is None:
                raise StorageError('论文快照不可用，请稍后重试')
            with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
                raw = stream.read(32 * 1024 * 1024 + 1)
            if len(raw) > 32 * 1024 * 1024 or not raw.startswith(b'SQLite format 3\0'):
                raise StorageError('论文快照格式无效或超过 32 MiB')
            path.write_bytes(raw)
            with closing(sqlite3.connect(path)) as connection:
                if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise StorageError('论文快照完整性检查失败')
        else:
            initialize(local_settings)
            # A stable version for seed-only cold starts and consistent ETags.
            with connect(path) as connection:
                seed_hash = hashlib.sha256()
                for seed in (settings.papers_seed_path, settings.researchers_seed_path,
                             settings.scholar_reviews_seed_path):
                    if seed and seed.exists():
                        seed_hash.update(seed.read_bytes())
                set_metadata(connection, 'snapshot_version', f'seed-{seed_hash.hexdigest()[:20]}')
                set_metadata(connection, 'last_sync_at', '')
        if write and keys:
            initialize(local_settings)
        yield local_settings
        if write:
            # backup() includes committed WAL data and produces one portable file.
            backup_path = Path(directory) / 'snapshot.db'
            with closing(sqlite3.connect(path)) as source, closing(sqlite3.connect(backup_path)) as target:
                source.backup(target)
            payload = gzip.compress(backup_path.read_bytes(), mtime=0)
            if len(payload) > 16 * 1024 * 1024:
                raise StorageError('论文快照过大，请迁移至数据库')
            # Two writers from revision N contend for the same immutable N+1 key.
            # Losing writers fail with 409, never overwrite the winning snapshot.
            store.create(snapshot_key(revision + 1), payload)
