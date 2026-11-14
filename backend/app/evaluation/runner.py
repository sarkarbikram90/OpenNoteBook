"""OpenNotebook — evaluation runner.

Orchestrates an evaluation run: for each gold case, retrieves chunk IDs, obtains
an answer (optional), scores retrieval and answer quality (optional LLM judge),
and aggregates an :class:`EvalReport`.

Retrieval, answer generation, and judging are injected as callables so the same
runner works against live services or recorded fixtures (used by the regression
suite in CI).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from app.evaluation.metrics import (
    answer_contains_all,
    answer_contains_none,
    is_dont_know,
    recall_at_k,
    reciprocal_rank,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from app.evaluation.dataset import EvalCase, EvalDataset
    from app.evaluation.judge import GroundednessResult


@dataclass
class CaseResult:
    """Per-case evaluation metrics."""

    id: str
    recall_at_k: float
    reciprocal_rank: float
    passed_contains: bool = True
    passed_forbidden: bool = True
    dont_know_correct: bool | None = None
    groundedness: float | None = None
    hallucinated: bool | None = None


@dataclass
class EvalReport:
    """Aggregated evaluation report."""

    dataset: str
    k: int
    total: int
    mean_recall_at_k: float
    mean_reciprocal_rank: float
    contain_pass_rate: float
    forbidden_pass_rate: float
    dont_know_accuracy: float | None = None
    mean_groundedness: float | None = None
    hallucination_rate: float | None = None
    cases: list[CaseResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return asdict(self)


def _mean(values: list[float]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def build_report(
    dataset_name: str,
    results: list[CaseResult],
    k: int,
) -> EvalReport:
    """Aggregate per-case results into a report."""
    total = len(results)
    return EvalReport(
        dataset=dataset_name,
        k=k,
        total=total,
        mean_recall_at_k=_mean([r.recall_at_k for r in results]) or 0.0,
        mean_reciprocal_rank=_mean([r.reciprocal_rank for r in results]) or 0.0,
        contain_pass_rate=_mean([1.0 if r.passed_contains else 0.0 for r in results]) or 0.0,
        forbidden_pass_rate=_mean([1.0 if r.passed_forbidden else 0.0 for r in results]) or 0.0,
        dont_know_accuracy=_mean(
            [
                1.0 if r.dont_know_correct else 0.0
                for r in results
                if r.dont_know_correct is not None
            ]
        )
        if any(r.dont_know_correct is not None for r in results)
        else None,
        mean_groundedness=_mean([r.groundedness for r in results if r.groundedness is not None]),
        hallucination_rate=_mean(
            [1.0 if r.hallucinated else 0.0 for r in results if r.hallucinated is not None]
        )
        if any(r.hallucinated is not None for r in results)
        else None,
        cases=results,
    )


async def run_eval(
    dataset: EvalDataset,
    retrieve_fn: Callable[[EvalCase], list[str]],
    answer_fn: Callable[[EvalCase], Awaitable[str]] | None = None,
    judge_fn: Callable[[EvalCase, str], Awaitable[GroundednessResult]] | None = None,
    k: int = 10,
) -> EvalReport:
    """Run the evaluation dataset and return an aggregated report.

    Args:
        dataset: gold cases.
        retrieve_fn: returns the top retrieved chunk IDs for a case.
        answer_fn: optional async function returning the generated answer.
        judge_fn: optional async groundedness judge.
        k: retrieval cutoff for recall@k.
    """
    results: list[CaseResult] = []

    for case in dataset.cases:
        retrieved = list(retrieve_fn(case))
        relevant = case.relevant_ids

        result = CaseResult(
            id=case.id,
            recall_at_k=recall_at_k(retrieved, relevant, k),
            reciprocal_rank=reciprocal_rank(retrieved, relevant),
        )

        if answer_fn is not None:
            answer = await answer_fn(case)
            if case.answer_must_contain:
                result.passed_contains = answer_contains_all(answer, case.answer_must_contain)
            if case.answer_must_not_contain:
                result.passed_forbidden = answer_contains_none(answer, case.answer_must_not_contain)
            result.dont_know_correct = is_dont_know(answer) == case.should_say_dont_know

            if judge_fn is not None:
                judgment = await judge_fn(case, answer)
                result.groundedness = judgment.score
                result.hallucinated = judgment.hallucinated

        results.append(result)

    return build_report(dataset.name, results, k)
