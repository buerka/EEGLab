"""Build a Linux Python 3.10 SCF ZIP, including runtime dependencies.

Run in GitHub Actions or a Linux Python 3.10 environment. This command only
creates a local artifact; it never uploads code or changes cloud resources.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-only', action='store_true', help='Source archive for inspection, not deployment')
    args = parser.parse_args()
    if not args.source_only and (sys.platform != 'linux' or sys.version_info[:2] != (3, 10)):
        parser.error('部署包必须在 Linux Python 3.10 下构建；请使用 GitHub Actions 或 --source-only')
    output = ROOT / 'output'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='eeglab-scf-', dir=output) as directory:
        stage = Path(directory)
        for name in ('app', 'data'):
            (stage / name).mkdir()
        for source in (ROOT / 'backend/app').glob('*.py'):
            if source.name not in {'main.py', 'cli.py', 'scheduler.py', 'cloud_api.py'}:
                shutil.copy2(source, stage / 'app' / source.name)
        for name in ('papers.toml', 'researchers.toml', 'scholar_reviews.toml'):
            shutil.copy2(ROOT / 'backend/data' / name, stage / 'data' / name)
        shutil.copy2(ROOT / 'deploy/scf/index.py', stage / 'index.py')
        requirements = ROOT / 'cloud-functions/requirements.txt'
        shutil.copy2(requirements, stage / 'requirements.txt')
        if not args.source_only:
            subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-compile',
                            '--target', str(stage), '-r', str(requirements)], check=True)
        destination = output / ('eeglab-scf-source.zip' if args.source_only else 'eeglab-scf-python310.zip')
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
            for source in sorted(stage.rglob('*')):
                if source.is_file() and '__pycache__' not in source.parts:
                    archive.write(source, source.relative_to(stage).as_posix())
        print(destination)


if __name__ == '__main__':
    main()
