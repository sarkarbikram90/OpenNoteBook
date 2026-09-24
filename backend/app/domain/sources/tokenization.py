"""OpenNotebook — Token counting for chunk sizing.

Chunk sizing is expressed in tokens. This module prefers a real BPE tokenizer
(``tiktoken``) when installed and falls back to a word-count heuristic otherwise,
so the pipeline works in a minimal environment and improves automatically when
the optional dependency is present.

Note: the heuristic and tiktoken's ``cl100k_base`` are *proxies* for the actual
BGE tokenizer. They are close enough for chunk-boundary decisions; exact BGE
token counts are not required for retrieval quality.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_WORD_TO_TOKEN_RATIO = 1.33

_encoder: Any = None
_encoder_checked = False


def _get_encoder() -> Any:
    """Lazily resolve a tiktoken encoder, or None when unavailable."""
    global _encoder, _encoder_checked
    if not _encoder_checked:
        _encoder_checked = True
        try:
            import tiktoken

            _encoder = tiktoken.get_encoding("cl100k_base")
            logger.info("Token counting using tiktoken cl100k_base")
        except Exception as exc:  # ImportError or download failure
            _encoder = None
            logger.info("tiktoken unavailable (%s); using word-count heuristic", exc)
    return _encoder


def count_tokens(text: str) -> int:
    """Return an estimated token count for ``text``."""
    if not text:
        return 0

    encoder = _get_encoder()
    if encoder is not None:
        try:
            return len(encoder.encode(text, disallowed_special=()))
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("tiktoken encode failed (%s); using heuristic", exc)

    return int(len(text.split()) * _WORD_TO_TOKEN_RATIO)


def encoding_name() -> str:
    """Return the active token counting backend name (for logs/diagnostics)."""
    return "tiktoken:cl100k_base" if _get_encoder() is not None else "word-heuristic"
