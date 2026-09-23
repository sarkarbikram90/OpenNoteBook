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
