"""OpenNotebook — tests for pure evaluation metrics."""

from __future__ import annotations

from app.evaluation.metrics import (
    answer_contains_all,
    answer_contains_none,
    is_dont_know,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k_perfect():
    assert recall_at_k(["a", "b", "c"], ["a", "b"], 3) == 1.0


def test_recall_at_k_partial():
    assert recall_at_k(["a", "x"], ["a", "b"], 2) == 0.5


def test_recall_at_k_respects_cutoff():
    assert recall_at_k(["x", "y", "a"], ["a"], 2) == 0.0
    assert recall_at_k(["x", "y", "a"], ["a"], 3) == 1.0


def test_recall_at_k_vacuous_when_no_relevant():
    assert recall_at_k(["a"], [], 5) == 1.0


def test_reciprocal_rank_first_hit():
    assert reciprocal_rank(["x", "a", "b"], ["a"]) == 0.5


def test_reciprocal_rank_no_hit():
    assert reciprocal_rank(["x", "y"], ["a"]) == 0.0


def test_answer_contains_all_case_insensitive():
    assert answer_contains_all("Refunds within 30 Days", ["30 days"]) is True
    assert answer_contains_all("Refunds within 30 days", ["30 days", "policy"]) is False


def test_answer_contains_none():
    assert answer_contains_none("Refunds within 30 days", ["60 days"]) is True
    assert answer_contains_none("Refunds within 60 days", ["60 days"]) is False


def test_is_dont_know_detection():
    assert is_dont_know("I could not find that information in this notebook's sources.") is True
    assert is_dont_know("I do not have sufficient information in the provided sources.") is True
    assert is_dont_know("The refund window is 30 days.") is False
