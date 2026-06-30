"""Background scheduler that refreshes history-enabled Live datasets.

So that history keeps accumulating even when no frontend is requesting data,
an APScheduler ``BackgroundScheduler`` fires one interval job per
history-enabled source at the source's ``refresh_seconds`` cadence and calls
``DatasetService.refresh(data_id, force=True)`` — each successful fetch records
a capture in ``history.sqlite``.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


def _make_job(dataset_service, data_id):
    def job():
        try:
            dataset_service.refresh(data_id, force=True)
        except Exception as err:  # pragma: no cover - upstream/network failure
            logger.warning("%s refresh failed: %s", data_id, err)

    return job


def start_history_poller(dataset_service, sources):
    """Start and return a BackgroundScheduler, or None if nothing to poll."""
    scheduler = BackgroundScheduler(daemon=True)
    job_count = 0
    for data_id, source in (sources or {}).items():
        history = source.get("history") or {}
        if not history.get("enabled"):
            continue
        interval = int(source.get("refresh_seconds", 600))
        scheduler.add_job(
            _make_job(dataset_service, data_id),
            trigger="interval",
            seconds=interval,
            id=f"history-poll-{data_id}",
            next_run_time=datetime.now(),  # seed one capture immediately
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        job_count += 1

    if not job_count:
        return None

    scheduler.start()
    logger.info("history-poller started (%d dataset(s))", job_count)
    return scheduler
