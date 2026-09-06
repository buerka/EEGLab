"""Small COS object store using Tencent's official Python SDK.

Objects are private. Conditional creation is the concurrency primitive; bucket
versioning must stay disabled because COS otherwise ignores forbid-overwrite.
"""
from __future__ import annotations

import json
import os
import re

from .budget import remaining_timeout


class StorageError(RuntimeError):
    pass


class WriteConflict(StorageError):
    pass


class CosStore:
    def __init__(self):
        from qcloud_cos import CosConfig, CosS3Client

        region = os.getenv('COS_REGION', 'ap-shanghai')
        if region not in {'ap-beijing', 'ap-shanghai', 'ap-guangzhou', 'ap-chengdu',
                          'ap-chongqing', 'ap-nanjing', 'ap-beijing-fsi',
                          'ap-shanghai-fsi', 'ap-shenzhen-fsi'}:
            raise StorageError('COS_REGION 必须配置为腾讯云中国大陆地域')
        self.bucket = os.getenv('COS_BUCKET', '')
        self.prefix = os.getenv('COS_PREFIX', 'eeglab/production').strip('/')
        if not re.fullmatch(r'[a-z0-9-]+-\d+', self.bucket):
            raise StorageError('缺少或无效的 COS_BUCKET（须包含 APPID）')
        if not re.fullmatch(r'[A-Za-z0-9/_-]+', self.prefix):
            raise StorageError('无效的 COS_PREFIX')
        secret_id = os.getenv('COS_SECRET_ID') or os.getenv('TENCENTCLOUD_SECRETID')
        secret_key = os.getenv('COS_SECRET_KEY') or os.getenv('TENCENTCLOUD_SECRETKEY')
        token = os.getenv('COS_SESSION_TOKEN') or os.getenv('TENCENTCLOUD_SESSIONTOKEN')
        if not secret_id or not secret_key:
            raise StorageError('未配置 COS 凭据或 SCF 执行角色')
        config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key,
                           Token=token, Scheme='https', Timeout=8)
        self.client = CosS3Client(config, retry=0)
        self._checked = False

    def _key(self, key: str) -> str:
        return f'{self.prefix}/{key}'

    def check_writes(self) -> None:
        if not self._checked:
            result = self._call(self.client.get_bucket_versioning, Bucket=self.bucket)
            if result.get('Status'):
                raise StorageError('请使用从未开启版本控制的独立 COS 桶，确保条件写入有效')
            self._checked = True

    def get(self, key: str) -> bytes | None:
        remaining_timeout(8)
        try:
            result = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
            stream = result['Body'].get_raw_stream()
            try:
                content = stream.read(16 * 1024 * 1024 + 1)
                if len(content) > 16 * 1024 * 1024:
                    raise StorageError('对象超过 16 MiB 安全上限')
                return content
            finally:
                stream.close()
        except Exception as exc:
            if getattr(exc, 'get_error_code', lambda: '')() == 'NoSuchKey':
                return None
            if isinstance(exc, StorageError):
                raise
            raise StorageError('COS 读取失败，请检查权限、地域和日志') from exc

    def create(self, key: str, value: bytes) -> None:
        self.check_writes()
        self._call(self.client.put_object, Bucket=self.bucket, Key=self._key(key),
                   Body=value, ContentType='application/octet-stream',
                   CacheControl='no-store', Metadata={'x-cos-forbid-overwrite': 'true'})

    def list(self, prefix: str, *, limit: int | None = None, marker: str = '') -> list[str]:
        found: list[str] = []
        next_marker = self._key(marker) if marker else ''
        while True:
            result = self._call(self.client.list_objects, Bucket=self.bucket,
                                Prefix=self._key(prefix), Marker=next_marker,
                                MaxKeys=min(1000, limit - len(found)) if limit else 1000)
            found.extend(item['Key'][len(self.prefix) + 1:]
                         for item in result.get('Contents', []))
            if limit and len(found) >= limit:
                return found[:limit]
            if str(result.get('IsTruncated', 'false')).lower() != 'true':
                return found
            marker_value = result.get('NextMarker')
            if not marker_value or marker_value == next_marker:
                raise StorageError('COS 列举分页未前进')
            next_marker = marker_value

    def delete(self, keys: list[str]) -> None:
        # Called only for already-aggregated anonymous events older than 32 days.
        for offset in range(0, len(keys), 1000):
            result = self._call(self.client.delete_objects, Bucket=self.bucket,
                               Delete={'Object': [{'Key': self._key(key)}
                                                  for key in keys[offset:offset + 1000]],
                                       'Quiet': 'true'})
            if result.get('Error'):
                raise StorageError('部分过期统计记录清理失败')

    @staticmethod
    def _call(method, **kwargs):
        remaining_timeout(8)
        try:
            return method(**kwargs)
        except Exception as exc:
            code = getattr(exc, 'get_error_code', lambda: '')()
            if code == 'FileAlreadyExists':
                raise WriteConflict('数据已被另一实例更新，请重试') from exc
            raise StorageError(f'COS 操作失败 ({code or type(exc).__name__})') from exc


def get_json(store, key: str):
    value = store.get(key)
    return json.loads(value) if value is not None else None


def create_json(store, key: str, value) -> None:
    store.create(key, json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())
