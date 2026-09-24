"""OpenNotebook — tests for the LLM-as-judge groundedness scorer."""

from __future__ import annotations

from app.evaluation.judge import parse_groundedness, score_groundedness


class FakeProvider:
    """Minimal provider returning a canned response."""

    name = "fake"

    def __init__(self, response: str) -> None:
        self._response = response

    async def generate(self, prompt: str, *, model: str | None = None, temperature: float | None = None) -> str:
        return self._response


def test_parse_direct_json():
    result = parse_groundedness('{"score": 0.9, "hallucinated": false, "reason": "ok"}')
    assert result.score == 0.9
    assert result.hallucinated is False


def test_parse_fenced_json():
    raw = 'Here is the answer:\n```json\n{"score": 0.4, "hallucinated": true}\n```'
    result = parse_groundedness(raw)
    assert result.score == 0.4
    assert result.hallucinated is True


def test_parse_clamps_and_defaults_hallucination():
    result = parse_groundedness('{"score": 1.7}')
    assert result.score == 1.0
    assert result.hallucinated is False


def test_parse_unparseable_is_conservative():
    result = parse_groundedness("not json at all")
    assert result.score == 0.0
    assert result.hallucinated is True


async def test_score_groundedness_uses_provider():
    provider = FakeProvider('{"score": 0.8, "hallucinated": false, "reason": "grounded"}')
    result = await score_groundedness(provider, "q", "answer", ["context text"])
    assert result.score == 0.8
    assert result.reason == "grounded"
