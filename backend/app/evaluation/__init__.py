"""OpenNotebook — RAG evaluation harness."""

from app.evaluation.dataset import EvalCase, EvalDataset, load_dataset
from app.evaluation.judge import GroundednessResult, parse_groundedness, score_groundedness
from app.evaluation.metrics import (
    answer_contains_all,
    answer_contains_none,
    is_dont_know,
    recall_at_k,
    reciprocal_rank,
)
from app.evaluation.runner import CaseResult, EvalReport, run_eval

__all__ = [
    "CaseResult",
    "EvalCase",
    "EvalDataset",
    "EvalReport",
    "GroundednessResult",
    "answer_contains_all",
    "answer_contains_none",
    "is_dont_know",
    "load_dataset",
    "parse_groundedness",
    "recall_at_k",
    "reciprocal_rank",
    "run_eval",
    "score_groundedness",
]
