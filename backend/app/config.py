from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(',') if item.strip())


def _load_env_file(path: Path) -> None:
    """加载本地 .env，但绝不覆盖系统或容器已经注入的变量。"""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding='utf-8-sig').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        elif ' #' in value:
            value = value.split(' #', 1)[0].rstrip()
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    database_path: Path
    researchers_seed_path: Path
    papers_seed_path: Path
    openalex_api_key: str | None
    sync_token: str | None
    allowed_origins: tuple[str, ...]
    cache_control: str
    sync_interval_seconds: int
    sync_minimum_ratio: float
    serpapi_api_key: str | None = None
    scholar_match_threshold: float = 0.94
    scholar_minimum_ratio: float = 0.5
    scholar_reviews_seed_path: Path | None = None
    analytics_database_path: Path | None = None
    analytics_hmac_secret: str | None = None
    analytics_cache_control: str = (
        'public, max-age=15, s-maxage=60, stale-while-revalidate=300'
    )
    analytics_dedupe_seconds: int = 30
    analytics_initial_total: int = 0


def get_settings() -> Settings:
    _load_env_file(BACKEND_ROOT / '.env')
    sync_token = os.getenv('PAPERS_SYNC_TOKEN') or None
    return Settings(
        database_path=Path(
            os.getenv('PAPERS_DATABASE_PATH', BACKEND_ROOT / 'data' / 'papers.db')
        ).resolve(),
        researchers_seed_path=Path(
            os.getenv('RESEARCHERS_SEED_PATH', BACKEND_ROOT / 'data' / 'researchers.toml')
        ).resolve(),
        papers_seed_path=Path(
            os.getenv('PAPERS_SEED_PATH', BACKEND_ROOT / 'data' / 'papers.toml')
        ).resolve(),
        openalex_api_key=os.getenv('OPENALEX_API_KEY') or None,
        sync_token=sync_token,
        allowed_origins=_split_csv(
            os.getenv('PAPERS_ALLOWED_ORIGINS', 'http://localhost:4321')
        ),
        cache_control=os.getenv(
            'PAPERS_CACHE_CONTROL',
            'public, max-age=0, s-maxage=60, stale-while-revalidate=300',
        ),
        sync_interval_seconds=max(
            300, int(os.getenv('PAPERS_SYNC_INTERVAL_SECONDS', '86400'))
        ),
        sync_minimum_ratio=min(
            1.0, max(0.1, float(os.getenv('PAPERS_SYNC_MINIMUM_RATIO', '0.8')))
        ),
        serpapi_api_key=os.getenv('SERPAPI_API_KEY') or None,
        scholar_match_threshold=min(
            1.0, max(0.8, float(os.getenv('SCHOLAR_MATCH_THRESHOLD', '0.94')))
        ),
        scholar_minimum_ratio=min(
            1.0, max(0.1, float(os.getenv('SCHOLAR_MINIMUM_RATIO', '0.5')))
        ),
        scholar_reviews_seed_path=Path(
            os.getenv(
                'SCHOLAR_REVIEWS_SEED_PATH',
                BACKEND_ROOT / 'data' / 'scholar_reviews.toml',
            )
        ).resolve(),
        analytics_database_path=Path(
            os.getenv(
                'ANALYTICS_DATABASE_PATH', BACKEND_ROOT / 'data' / 'analytics.db'
            )
        ).resolve(),
        analytics_hmac_secret=(
            os.getenv('ANALYTICS_HMAC_SECRET') or sync_token or None
        ),
        analytics_cache_control=os.getenv(
            'ANALYTICS_CACHE_CONTROL',
            'public, max-age=15, s-maxage=60, stale-while-revalidate=300',
        ),
        analytics_dedupe_seconds=max(
            5, min(3600, int(os.getenv('ANALYTICS_DEDUPE_SECONDS', '30')))
        ),
        analytics_initial_total=max(
            0, int(os.getenv('ANALYTICS_INITIAL_TOTAL', '0'))
        ),
    )
