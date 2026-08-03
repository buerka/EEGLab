from __future__ import annotations

import logging
import time

from .config import get_settings
from .database import initialize
from .sync_service import sync_all_researchers


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)


def main() -> None:
    settings = get_settings()
    initialize(settings)
    while True:
        try:
            result = sync_all_researchers(settings)
            logging.info('publication sync completed: %s', result.as_dict())
        except Exception:
            logging.exception('publication sync failed; serving previous snapshot')
        time.sleep(settings.sync_interval_seconds)


if __name__ == '__main__':
    main()
