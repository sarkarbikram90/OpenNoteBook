"""OpenNotebook — CLI to run the evaluation harness against live services.

Usage:
    python -m app.scripts.run_eval <dataset.json> --k 10 --output report.json

Requires running Postgres/Qdrant/LLM (e.g. docker compose up). The CI regression
suite uses recorded fixtures instead (see tests/evaluation/test_regression.py).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.evaluation.dataset import EvalCase, load_dataset


def _admin_context() -> Any:
    from app.domain.retrieval.retriever import UserSecurityContext

    # Evaluation runs with full clearance so metrics reflect retrieval quality,
    # not the ACL of a particular user.
    return UserSecurityContext(user_id="eval", roles=["admin"], max_sensitivity="restricted")


def _retrieve_ids(case: EvalCase) -> list[str]:
    from app.domain.retrieval.retriever import retrieve

    result = retrieve(
        query=case.question,
        notebook_id=case.notebook_id or "",
        security_context=_admin_context(),
    )
    return [c.chunk_id for c in result.chunks]


def _retrieve_chunks(case: EvalCase) -> list[Any]:
    from app.domain.retrieval.retriever import retrieve

    return retrieve(
        query=case.question,
        notebook_id=case.notebook_id or "",
        security_context=_admin_context(),
    ).chunks


async def _main(args: argparse.Namespace) -> int:
    from app.evaluation.judge import GroundednessResult, score_groundedness
    from app.evaluation.runner import run_eval
    from app.infrastructure.llm import get_llm_provider

    dataset = load_dataset(args.dataset)
    provider = get_llm_provider()

    async def answer_fn(case: EvalCase) -> str:
        from app.domain.chat.orchestrator import GroundedPromptBuilder

        prompt, _ = GroundedPromptBuilder.build_prompt(
            query=case.question, chunks=_retrieve_chunks(case), history_messages=None
        )
        return await provider.generate(prompt)

    async def judge_fn(case: EvalCase, answer: str) -> GroundednessResult:
        contexts = [c.text for c in _retrieve_chunks(case)]
        return await score_groundedness(provider, case.question, answer, contexts)

    report = await run_eval(
        dataset=dataset,
        retrieve_fn=_retrieve_ids,
        answer_fn=None if args.retrieval_only else answer_fn,
        judge_fn=None if (args.retrieval_only or args.no_judge) else judge_fn,
        k=args.k,
    )

    output = Path(args.output)
    output.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    summary = {key: value for key, value in report.to_dict().items() if key != "cases"}
    print(json.dumps(summary, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the OpenNotebook evaluation harness")
    parser.add_argument("dataset", help="Path to a gold Q&A dataset JSON file")
    parser.add_argument("--k", type=int, default=10, help="Recall cutoff (default 10)")
    parser.add_argument("--output", default="eval_report.json", help="Report output path")
    parser.add_argument("--retrieval-only", action="store_true", help="Skip answer generation")
    parser.add_argument("--no-judge", action="store_true", help="Skip LLM groundedness judging")
    args = parser.parse_args()
    return asyncio.run(_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
