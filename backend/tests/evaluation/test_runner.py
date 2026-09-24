"""OpenNotebook — tests for the evaluation runner aggregation."""

from __future__ import annotations

from app.evaluation.dataset import EvalCase, EvalDataset
from app.evaluation.judge import GroundednessResult
from app.evaluation.runner import run_eval


async def test_run_eval_aggregates_retrieval_and_answer_metrics():
    dataset = EvalDataset(
        name="unit",
        cases=[
            EvalCase(id="c1", question="Q1", expected_chunk_ids=["k1"], answer_must_contain=["yes"]),
            EvalCase(id="c2", question="Q2", expected_chunk_ids=["k2"], should_say_dont_know=True),
        ],
    )

    recorded = {
        "c1": "Yes, that is correct. [Source 1]",
        "c2": "I could not find that information in this notebook's sources.",
    }

    async def answer_fn(case: EvalCase) -> str:
        return recorded[case.id]

    async def judge_fn(case: EvalCase, answer: str) -> GroundednessResult:
        return GroundednessResult(score=0.9, hallucinated=False)

    report = await run_eval(
        dataset,
        retrieve_fn=lambda case: ["k1", "k9"] if case.id == "c1" else ["k2"],
        answer_fn=answer_fn,
        judge_fn=judge_fn,
        k=10,
    )

    assert report.total == 2
    assert report.mean_recall_at_k == 1.0
    assert report.contain_pass_rate == 1.0
    assert report.forbidden_pass_rate == 1.0
    assert report.dont_know_accuracy == 1.0
    assert report.mean_groundedness == 0.9
    assert report.hallucination_rate == 0.0


async def test_run_eval_retrieval_only():
    dataset = EvalDataset(
        name="retrieval-only",
        cases=[EvalCase(id="c1", question="Q1", expected_chunk_ids=["k1", "k2"])],
    )
    report = await run_eval(dataset, retrieve_fn=lambda case: ["k1"], k=10)

    assert report.total == 1
    assert report.mean_recall_at_k == 0.5
    assert report.dont_know_accuracy is None
    assert report.mean_groundedness is None
