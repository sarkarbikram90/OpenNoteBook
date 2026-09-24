"""OpenNotebook — connector schedule evaluation.

Determines whether a connector's cron schedule is due, based on its last sync
time. Kept free of Celery/DB imports so it can be unit tested directly.
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.domain.connectors.timeutil import ensure_utc

logger = logging.getLogger(__name__)


def is_schedule_due(
    cron_expr: str | None,
    now: datetime,
    last_run: datetime | None,
) -> bool:
    """Return True if a connector with ``cron_expr`` is due for a sync.

    Args:
        cron_expr: standard 5-field cron expression (e.g. ``*/15 * * * *``).
        now: current time.
        last_run: the connector's ``last_sync_at`` (None = never synced).

    Returns:
        True when the next scheduled run after ``last_run`` has arrived.
        A never-synced connector is considered due immediately.
    """
    if not cron_expr:
        return False

    if last_run is None:
        return True

    from croniter import croniter

    now_utc = ensure_utc(now)
    last_utc = ensure_utc(last_run)
    if now_utc is None or last_utc is None:
        return False

    try:
        next_run = croniter(cron_expr, last_utc).get_next(datetime)
    except (ValueError, KeyError) as exc:
        logger.warning("Invalid cron expression %r: %s", cron_expr, exc)
        return False

    next_run_utc = ensure_utc(next_run)
    return bool(next_run_utc is not None and next_run_utc <= now_utc)
