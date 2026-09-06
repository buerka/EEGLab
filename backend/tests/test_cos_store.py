from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.cos_store import CosStore, StorageError, WriteConflict


class CosSdkContractTests(unittest.TestCase):
    def setUp(self):
        try:
            import qcloud_cos
        except ImportError:
            self.skipTest('Install cloud-functions/requirements.txt to test the COS SDK contract')
        with patch.dict(os.environ, {'COS_REGION': 'ap-shanghai', 'COS_BUCKET': 'test-1250000000',
                                     'COS_PREFIX': 'lab/test', 'COS_SECRET_ID': 'fake-id',
                                     'COS_SECRET_KEY': 'fake-key'}, clear=True):
            self.store = CosStore()

    def test_real_sdk_passes_the_conditional_creation_header(self):
        with patch.object(self.store.client, 'get_bucket_versioning', return_value={}), \
             patch.object(self.store.client, 'send_request', return_value=SimpleNamespace(headers={})) as send:
            self.store.create('snapshot', b'example')
        self.assertEqual(send.call_args.kwargs['headers']['x-cos-forbid-overwrite'], 'true')
        self.assertEqual(send.call_args.kwargs['data'], b'example')
        self.assertIn('cos.ap-shanghai.myqcloud.com', send.call_args.kwargs['url'])

    def test_bucket_versioning_disables_writes(self):
        for value in ('Enabled', 'Suspended'):
            with patch.object(self.store.client, 'get_bucket_versioning', return_value={'Status': value}), \
                 patch.object(self.store.client, 'put_object') as put:
                with self.assertRaises(StorageError):
                    self.store.create('snapshot', b'example')
                put.assert_not_called()

    def test_real_sdk_conflict_is_not_retried_as_an_overwrite(self):
        from qcloud_cos.cos_exception import CosServiceError
        error = CosServiceError('PUT', {'code': 'FileAlreadyExists', 'message': 'exists'}, 409)
        with patch.object(self.store.client, 'get_bucket_versioning', return_value={}), \
             patch.object(self.store.client, 'send_request', side_effect=error) as send:
            with self.assertRaises(WriteConflict):
                self.store.create('snapshot', b'example')
        self.assertEqual(send.call_count, 1)

    def test_pagination_keeps_the_prefix_and_marker(self):
        with patch.object(self.store.client, 'list_objects', side_effect=[
            {'Contents': [{'Key': 'lab/test/events/a'}], 'IsTruncated': 'true', 'NextMarker': 'lab/test/events/a'},
            {'Contents': [{'Key': 'lab/test/events/b'}], 'IsTruncated': 'false'},
        ]) as listing:
            self.assertEqual(self.store.list('events/'), ['events/a', 'events/b'])
        self.assertEqual(listing.call_args.kwargs['Marker'], 'lab/test/events/a')
        self.assertEqual(listing.call_args.kwargs['Prefix'], 'lab/test/events/')
