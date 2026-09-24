"""OpenNotebook — fixtures-based evaluation regression suite.

Runs entirely on recorded outputs, so it executes in CI without Postgres, Qdrant,
or an LLM. It fails the build if retrieval/answer quality drops below thresholds.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.evaluation.dataset import EvalDataset
from app.evaluation.runner import EvalReport, run_eval

FIXTURE = Path(__file__).parent / "fixtures" / "baseline.json"

# Regression thresholds — quality must not fall below these.
MIN_MEAN_RECALL_AT_K = 0.9
MIN_CONTAIN_PASS_RATE = 1.0
MIN_FORBIDDEN_PASS_RATE = 1.0
MIN_DONT_KNOW_ACCURACY = 1.0


async def _evaluate() -> EvalReport:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    dataset = EvalDataset.model_validate(data["dataset"])
    recorded = data["recorded"]

    async def answer_fn(case) -> str:
        return recorded[case.id]["answer"]

    return await run_eval(
        dataset,
        retrieve_fn=lambda case: recorded[case.id]["retrieved"],
        answer_fn=answer_fn,
        k=10,
    )


async def test_baseline_meets_quality_thresholds():
    report = await _evaluate()

    assert report.total == 3, "baseline dataset size changed unexpectedly"
    assert report.mean_recall_at_k >= MIN_MEAN_RECALL_AT_K
    assert report.contain_pass_rate >= MIN_CONTAIN_PASS_RATE
    assert report.forbidden_pass_rate >= MIN_FORBIDDEN_PASS_RATE
    assert (report.dont_know_accuracy or 0.0) >= MIN_DONT_KNOW_ACCURACY
