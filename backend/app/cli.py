from __future__ import annotations

import argparse
import json

from .analytics import initialize_analytics
from .config import get_settings
from .database import initialize
from .sync_service import sync_all_researchers


def main() -> int:
    parser = argparse.ArgumentParser(description='论文后端管理工具')
    parser.add_argument('command', choices=('init', 'sync'))
    args = parser.parse_args()
    settings = get_settings()
    initialize(settings)
    initialize_analytics(settings)
    if args.command == 'sync':
        print(json.dumps(sync_all_researchers(settings).as_dict(), ensure_ascii=False, indent=2))
    else:
        print(f'数据库已初始化: {settings.database_path}')
        print(f'访问统计数据库已初始化: {settings.analytics_database_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
