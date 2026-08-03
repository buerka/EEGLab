from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import _load_env_file


class ConfigTestCase(unittest.TestCase):
    def test_env_file_loads_values_without_overriding_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text(
                'SERPAPI_API_KEY="from-file"\n'
                'OPENALEX_API_KEY=file-value # local comment\n'
                'export PAPERS_SYNC_TOKEN=token-value\n',
                encoding='utf-8',
            )
            with patch.dict(os.environ, {'SERPAPI_API_KEY': 'from-process'}, clear=False):
                for key in ('OPENALEX_API_KEY', 'PAPERS_SYNC_TOKEN'):
                    os.environ.pop(key, None)
                _load_env_file(path)
                self.assertEqual(os.environ['SERPAPI_API_KEY'], 'from-process')
                self.assertEqual(os.environ['OPENALEX_API_KEY'], 'file-value')
                self.assertEqual(os.environ['PAPERS_SYNC_TOKEN'], 'token-value')
                os.environ.pop('OPENALEX_API_KEY', None)
                os.environ.pop('PAPERS_SYNC_TOKEN', None)


if __name__ == '__main__':
    unittest.main()
