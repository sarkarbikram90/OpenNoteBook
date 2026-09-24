"""OpenNotebook — pure retrieval/answer metrics (no external dependencies).

These functions are intentionally dependency-free so they can be unit tested and
run in CI without a database, vector store, or LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# Phrases the system prompt uses for the grounded "I don't know" fallback.
DONT_KNOW_PHRASES: tuple[str, ...] = (
    "could not find that information",
    "do not have sufficient information",
    "don't have sufficient information",
)


def recall_at_k(retrieved: Iterable[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of relevant items found in the top-k retrieved items."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 1.0
    top_k = set(list(retrieved)[:k])
    return len(top_k & relevant_set) / len(relevant_set)


def reciprocal_rank(retrieved: Iterable[str], relevant: Iterable[str]) -> float:
    """Reciprocal of the rank of the first relevant item (0 if none)."""
    relevant_set = set(relevant)
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant_set:
            return 1.0 / rank
    return 0.0


def answer_contains_all(answer: str, required: Iterable[str]) -> bool:
    """True if every required substring appears (case-insensitive)."""
    low = answer.lower()
    return all(token.lower() in low for token in required)


def answer_contains_none(answer: str, forbidden: Iterable[str]) -> bool:
    """True if no forbidden substring appears (case-insensitive)."""
    low = answer.lower()
    return not any(token.lower() in low for token in forbidden)


def is_dont_know(answer: str) -> bool:
    """True if the answer uses the grounded 'I don't know' fallback."""
    low = answer.lower()
    return any(phrase in low for phrase in DONT_KNOW_PHRASES)
