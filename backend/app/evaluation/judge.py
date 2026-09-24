"""OpenNotebook — LLM-as-judge groundedness scoring.

Given a question, the retrieved context, and the generated answer, asks an LLM to
score how well the answer is grounded in the context and whether it hallucinated.
The prompt requests strict JSON so the result is machine-parseable.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

GROUNDEDNESS_PROMPT = """You are an impartial evaluator for a retrieval-augmented
question answering system.

Assess whether the ANSWER is fully grounded in the CONTEXT and does not introduce
facts that are absent from it.

Respond ONLY with a JSON object of the form:
{{"score": <number between 0 and 1>, "hallucinated": <true or false>,
"reason": "<short explanation>"}}

Scoring guide:
- 1.0 = every claim is supported by the context
- 0.5 = partially supported / some unsupported claims
- 0.0 = unsupported or contradicts the context

QUESTION:
{question}

CONTEXT:
{context}

ANSWER:
{answer}
"""


@dataclass
class GroundednessResult:
    """Result of a groundedness judgement."""

    score: float
    hallucinated: bool
    reason: str = ""


def parse_groundedness(raw: str) -> GroundednessResult:
    """Parse a judge response into a :class:`GroundednessResult`.

    Tolerates markdown fences and surrounding prose. Falls back to a conservative
    (score 0.0, hallucinated) result if no JSON object can be parsed.
    """
    text = raw.strip()

    candidate: dict[str, Any] | None = None
    try:
        candidate = json.loads(text)
    except json.JSONDecodeError:
        fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if fence:
            try:
                candidate = json.loads(fence.group(1).strip())
            except json.JSONDecodeError:
                candidate = None
        if candidate is None:
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                try:
                    candidate = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    candidate = None

    if not isinstance(candidate, dict) or "score" not in candidate:
        logger.warning("Could not parse groundedness response: %r", raw[:200])
        return GroundednessResult(score=0.0, hallucinated=True, reason="unparseable")

    try:
        score = float(candidate["score"])
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(1.0, score))

    hallucinated = bool(candidate.get("hallucinated", score < 0.5))
    reason = str(candidate.get("reason", ""))[:500]
    return GroundednessResult(score=score, hallucinated=hallucinated, reason=reason)


async def score_groundedness(
    provider: Any,
    question: str,
    answer: str,
    contexts: list[str],
    model: str | None = None,
) -> GroundednessResult:
    """Ask ``provider`` to judge how grounded ``answer`` is in ``contexts``."""
    prompt = GROUNDEDNESS_PROMPT.format(
        question=question,
        context="\n\n".join(contexts) or "(no context retrieved)",
        answer=answer,
    )
    raw = await provider.generate(prompt, model=model)
    return parse_groundedness(raw)
