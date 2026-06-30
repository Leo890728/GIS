"""Standalone history-capture worker.

Runs the same interval poller as the web app, but as a dedicated process so that
captures are decoupled from the web server lifecycle and never duplicated by a
multi-worker WSGI server. Point the web service at ``HISTORY_BACKGROUND_POLL=0``
and run this alongside it (see docker-compose.yml).

Run with: ``python -m backend.worker``
"""

import logging
import signal
import threading

from backend.config import CACHE_DB_PATH, DATA_SOURCES, HISTORY_DB_PATH
from backend.services.cache_db import CacheDb
from backend.services.dataset_service import DatasetService
from backend.services.history_db import HistoryDb
from backend.services.history_poller import start_history_poller

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    dataset_service = DatasetService(
        DATA_SOURCES,
        cache_db=CacheDb(CACHE_DB_PATH),
        history_db=HistoryDb(HISTORY_DB_PATH),
    )

    scheduler = start_history_poller(dataset_service, DATA_SOURCES)
    if scheduler is None:
        logger.info("no history-enabled datasets; nothing to capture, exiting")
        return

    # Block until SIGINT/SIGTERM (e.g. `docker stop`), then shut down cleanly.
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    stop.wait()
    logger.info("shutting down history-capture worker")
    scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
