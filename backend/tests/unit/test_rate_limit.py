"""OpenNotebook — Unit tests for the connector rate limiter."""

from __future__ import annotations

import pytest

from app.domain.connectors.rate_limit import RateLimiter


def test_non_positive_rate_rejected():
    with pytest.raises(ValueError):
        RateLimiter(0)


def test_first_acquire_does_not_sleep():
    slept: list[float] = []
    limiter = RateLimiter(1.0, time_func=lambda: 0.0, sleep_func=slept.append)
    limiter.acquire()
    assert slept == []


def test_second_acquire_sleeps_min_interval():
    slept: list[float] = []
    limiter = RateLimiter(2.0, time_func=lambda: 0.0, sleep_func=slept.append)
    limiter.acquire()
    limiter.acquire()
    assert slept == [0.5]


def test_context_manager_acquires():
    slept: list[float] = []
    with RateLimiter(10.0, time_func=lambda: 0.0, sleep_func=slept.append):
        pass
    assert slept == []
