"""OpenNotebook — Prompt-injection guardrails for user input.

Defence-in-depth for the RAG prompt: detects common prompt-injection attempts in
the user's question and neutralises our own prompt delimiters (``<question>``,
``<context>``, ``<system>``) so user input cannot break out of the ``<question>``
block. This is heuristic, not a guarantee.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Patterns that strongly indicate a prompt-injection attempt.
# Note: delimiter tags are NOT blocked here — they are neutralised below so that
# legitimate questions mentioning them are still answerable.
_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_instructions",
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts)", re.I),
    ),
    (
        "disregard_instructions",
        re.compile(r"disregard\s+(the\s+)?(previous|above|system|earlier)", re.I),
    ),
    (
        "reveal_prompt",
        re.compile(
            r"(reveal|show|print|repeat|output)\s+(me\s+)?(your\s+)?(system\s+)?(prompt|instructions)",
            re.I,
        ),
    ),
    ("jailbreak", re.compile(r"\b(jailbreak|developer\s+mode|DAN\s+mode)\b", re.I)),
    ("role_override", re.compile(r"you\s+are\s+now\s+(a|an|the)\b", re.I)),
]

# Our own prompt delimiters, neutralised in user input.
_DELIMITER_MAP = {
    "<system>": "<system_>",
    "</system>": "</system_>",
    "<context>": "<context_>",
    "</context>": "</context_>",
    "<question>": "<question_>",
    "</question>": "</question_>",
}
_DELIMITER_RE = re.compile(r"</?\s*(system|context|question)\s*>", re.I)


@dataclass
class GuardrailResult:
    """Outcome of evaluating a user prompt against the guardrails."""

    allowed: bool
    sanitized: str
    reason: str | None = None
    matches: list[str] = field(default_factory=list)


def neutralize_delimiters(text: str) -> str:
    """Disarm prompt-delimiter tags so user input cannot escape its block."""
    return _DELIMITER_RE.sub(lambda m: _DELIMITER_MAP.get(m.group(0).lower(), "<tag_>"), text)


def evaluate_prompt(question: str) -> GuardrailResult:
    """Evaluate a user question, returning whether it may proceed.

    Blocked prompts are returned with ``allowed=False`` and a ``reason``; benign
    prompts are returned with our delimiters neutralised in ``sanitized``.
    """
    matches = [name for name, pattern in _INJECTION_PATTERNS if pattern.search(question)]
    if matches:
        return GuardrailResult(
            allowed=False,
            sanitized=question,
            reason=matches[0],
            matches=matches,
        )

    return GuardrailResult(
        allowed=True,
        sanitized=neutralize_delimiters(question),
        matches=[],
    )
