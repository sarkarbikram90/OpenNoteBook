"""OpenNotebook — Unit tests for connector schedule evaluation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.connectors.scheduling import is_schedule_due

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def test_empty_cron_is_never_due():
    assert is_schedule_due("", NOW, NOW - timedelta(hours=1)) is False


def test_never_synced_connector_is_due():
    assert is_schedule_due("0 * * * *", NOW, None) is True


def test_due_when_next_run_has_passed():
    # Hourly cron, last run two hours ago -> next run (11:00) already passed.
    assert is_schedule_due("0 * * * *", NOW, NOW - timedelta(hours=2)) is True


def test_not_due_before_next_run():
    # Hourly cron, last run at 12:00 -> next run (13:00) is in the future.
    assert is_schedule_due("0 * * * *", NOW, NOW) is False


def test_due_exactly_at_boundary():
    # Hourly cron, last run at 11:50 -> next run (12:00) has arrived.
    assert is_schedule_due("0 * * * *", NOW, NOW - timedelta(minutes=10)) is True


def test_invalid_cron_is_not_due():
    assert is_schedule_due("not a cron", NOW, NOW - timedelta(hours=1)) is False


def test_naive_last_run_is_treated_as_utc():
    naive_last_run = datetime(2026, 6, 1, 10, 0)  # 10:00 UTC, resolved to 11:00 next
    assert is_schedule_due("0 * * * *", NOW, naive_last_run) is True
