from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / 'edgeone.json').read_text())
assert config['outputDirectory'] == 'frontend/dist'
assert config['cloudFunctions']['mainlandRegions'] == ['ap-shanghai']
assert 'overseasRegions' not in config['cloudFunctions']
assert not config.get('schedules'), 'SCF owns the authenticated timer; do not expose a public cron route'
vendor = ROOT / 'cloud-functions/api/_vendor'
assert (vendor / 'app/cloud_api.py').is_file(), 'Run npm run build first'
for source in vendor.rglob('*'):
    if source.is_file():
        assert source.suffix in {'.py', '.toml'}, f'Unexpected deployment file: {source}'
        if source.suffix == '.py':
            ast.parse(source.read_text(encoding='utf-8'), feature_version=(3, 10))
for source in (ROOT / 'cloud-functions').rglob('*.py'):
    ast.parse(source.read_text(encoding='utf-8'), feature_version=(3, 10))
dist = ROOT / 'frontend/dist'
assert len(list(dist.rglob('index.html'))) == 10
assert not list(dist.rglob('*.py'))
assert not list(dist.rglob('*.db'))
assert not list(dist.rglob('*.toml'))
assert not (dist / 'edgeone.json').exists()
for asset in dist.rglob('*'):
    if asset.is_file():
        assert asset.stat().st_size <= 25_000_000, f'Exceeds Makers single-file limit: {asset}'
print('Deployment inputs: 10 static pages, mainland region, Python 3.10 syntax, no private runtime files in dist.')
