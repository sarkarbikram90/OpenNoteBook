"""OpenNotebook — Unit tests for token counting."""

from __future__ import annotations

from app.domain.sources.tokenization import count_tokens, encoding_name


def test_empty_text_is_zero_tokens():
    assert count_tokens("") == 0


def test_single_word_is_at_least_one_token():
    assert count_tokens("hello") >= 1


def test_longer_text_has_more_tokens():
    short = count_tokens("hello world")
    long = count_tokens("hello world this is a considerably longer sentence with many tokens")
    assert long > short


def test_encoding_name_is_reported():
    assert encoding_name() in {"tiktoken:cl100k_base", "word-heuristic"}
