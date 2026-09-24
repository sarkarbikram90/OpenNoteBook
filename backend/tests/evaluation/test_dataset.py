"""OpenNotebook — tests for the evaluation dataset loader."""

from __future__ import annotations

import json

from app.evaluation.dataset import load_dataset


def test_load_dataset_parses_cases(tmp_path):
    path = tmp_path / "gold.json"
    path.write_text(
        json.dumps(
            {
                "name": "smoke",
                "cases": [
                    {"id": "c1", "question": "Q?", "expected_chunk_ids": ["k1"]},
                    {"id": "c2", "question": "Q2?", "expected_source_ids": ["s1"]},
                ],
            }
        ),
        encoding="utf-8",
    )

    dataset = load_dataset(path)
    assert dataset.name == "smoke"
    assert len(dataset.cases) == 2
    assert dataset.cases[0].relevant_ids == ["k1"]
    # Falls back to source IDs when chunk IDs are absent.
    assert dataset.cases[1].relevant_ids == ["s1"]
