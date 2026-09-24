"""OpenNotebook — connector time helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def ensure_utc(value: datetime | None) -> datetime | None:
    """Return a timezone-aware UTC datetime.

    Incoming watermarks may be naive (e.g. parsed from a query string without a
    timezone); comparisons against tz-aware source timestamps would otherwise
    raise TypeError. Naive values are assumed to be UTC.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
