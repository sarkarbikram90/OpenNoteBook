"""OpenNotebook — Unit tests for the embedding generator.

Validates that document passages are embedded WITHOUT instruction prefixes,
while search queries DO include instruction prefixes per BGE specifications.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.domain.sources.embedder import embed_texts


class TestEmbedderUnit:
    """Unit tests for embedding generation."""

    def test_empty_list_returns_empty_embeddings(self) -> None:
        """Passing an empty list returns immediately with empty list."""
        assert embed_texts([]) == []

    @patch("app.domain.sources.embedder._get_model")
    def test_query_embedding_includes_instruction_prefix(self, mock_get_model: MagicMock) -> None:
        """Search queries must include the BGE instruction prefix."""
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [[0.1, 0.2, 0.3]])
        mock_get_model.return_value = mock_model

        embed_texts(["What is transformer attention?"], is_query=True)

        mock_model.encode.assert_called_once()
        passed_texts = mock_model.encode.call_args[0][0]
        assert len(passed_texts) == 1
        assert passed_texts[0].startswith("Represent this sentence: ")
        assert "What is transformer attention?" in passed_texts[0]

    @patch("app.domain.sources.embedder._get_model")
    def test_document_chunk_embedding_has_no_instruction_prefix(self, mock_get_model: MagicMock) -> None:
        """Document passages must NOT include instruction prefixes to maintain fidelity."""
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [[0.4, 0.5, 0.6]])
        mock_get_model.return_value = mock_model

        passage = "This is a document paragraph explaining self-attention."
        embed_texts([passage], is_query=False)

        mock_model.encode.assert_called_once()
        passed_texts = mock_model.encode.call_args[0][0]
        assert len(passed_texts) == 1
        assert passed_texts[0] == passage
        assert not passed_texts[0].startswith("Represent this sentence: ")

    def test_vertex_ai_embedding_provider_uses_task_types(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When embedding_provider=vertex_ai, embed_texts delegates to Vertex AI with RETRIEVAL_QUERY/DOCUMENT."""
        from types import SimpleNamespace

        from app.domain.sources import embedder
        from app.infrastructure.embeddings import vertex_ai

        fake_settings = SimpleNamespace(
            embedding_provider="vertex_ai",
            embedding_batch_size=32,
            embedding_dimension=384,
            vertex_ai_embedding_model="text-embedding-004",
            vertex_ai_location="us-central1",
            gcs_project_id="test-project",
        )
        monkeypatch.setattr(embedder, "get_settings", lambda: fake_settings)
        monkeypatch.setattr(vertex_ai, "get_settings", lambda: fake_settings)
        monkeypatch.setattr(
            vertex_ai,
            "_get_adc_access_token",
            lambda: ("fake-adc-token", "test-project"),
        )

        captured_calls: list[dict] = []

        def fake_predict(texts, **kwargs):
            captured_calls.append({"texts": texts, **kwargs})
            return [[0.25] * kwargs["output_dimensionality"] for _ in texts]

        monkeypatch.setattr(vertex_ai, "_predict_vertex_batch", fake_predict)

        doc_vecs = embed_texts(["Document passage one"], is_query=False)
        query_vecs = embed_texts(["Search query one"], is_query=True)

        assert len(doc_vecs) == 1 and len(doc_vecs[0]) == 384
        assert len(query_vecs) == 1 and len(query_vecs[0]) == 384
        assert captured_calls[0]["task_type"] == "RETRIEVAL_DOCUMENT"
        assert captured_calls[1]["task_type"] == "RETRIEVAL_QUERY"
        assert captured_calls[0]["model_name"] == "text-embedding-004"

