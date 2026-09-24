"""OpenNotebook — Pluggable PII detection/redaction engine.

Provides a single entry point, :func:`get_pii_scrubber`, that returns either the
fast regex-based scrubber (:class:`~app.domain.governance.pii.PIIScrubber`) or the
Microsoft Presidio NER scrubber (:class:`PresidioPIIScrubber`) depending on
configuration. Both expose the same ``scrub(text, strategy) -> PIIScrubResult``
interface, so callers do not care which backend is active.

Selection (``pii_engine`` setting):
    regex     always use the regex scrubber
    presidio  always use Presidio (raises if not installed)
    auto      use Presidio when importable, otherwise fall back to regex (default)

Install Presidio with the optional extra:
    pip install -e "./backend[pii]"
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from app.domain.governance.pii import MaskingStrategy, PIIScrubber, PIIScrubResult

logger = logging.getLogger(__name__)


class PresidioPIIScrubber:
    """NER-based PII scrubber backed by Microsoft Presidio."""

    DEFAULT_ENTITIES: ClassVar[list[str]] = [
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "US_SSN",
        "IBAN_CODE",
        "US_PASSPORT",
        "US_DRIVER_LICENSE",
        "MEDICAL_LICENSE",
        "IP_ADDRESS",
        "CRYPTO",
        "LOCATION",
    ]

    def __init__(
        self,
        default_strategy: MaskingStrategy = MaskingStrategy.REDACT,
        entities: list[str] | None = None,
        score_threshold: float = 0.4,
    ) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "Presidio is not installed. Install the optional extra: "
                "pip install -e './backend[pii]'"
            ) from exc

        self.default_strategy = default_strategy
        self.entities = entities or self.DEFAULT_ENTITIES
        self.score_threshold = score_threshold
        self._analyzer: Any = AnalyzerEngine()
        self._anonymizer: Any = AnonymizerEngine()

    def _operators(self, strategy: MaskingStrategy) -> dict[str, Any]:
        """Map a masking strategy to a Presidio anonymizer operator config."""
        from presidio_anonymizer.entities import OperatorConfig

        if strategy == MaskingStrategy.MASK:
            return {
                "DEFAULT": OperatorConfig(
                    "mask",
                    {"masking_char": "*", "chars_to_mask": 4, "from_end": True},
                )
            }
        if strategy == MaskingStrategy.HASH:
            return {"DEFAULT": OperatorConfig("hash")}
        return {"DEFAULT": OperatorConfig("replace")}

    def scrub(self, text: str, strategy: MaskingStrategy | None = None) -> PIIScrubResult:
        """Detect and anonymize PII in ``text`` using Presidio NER."""
        strat = strategy or self.default_strategy
        results = self._analyzer.analyze(
            text=text,
            entities=self.entities,
            language="en",
            score_threshold=self.score_threshold,
        )

        entities_found: dict[str, int] = {}
        for result in results:
            entities_found[result.entity_type] = entities_found.get(result.entity_type, 0) + 1

        anonymized = self._anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=self._operators(strat),
        )

        return PIIScrubResult(
            cleaned_text=anonymized.text,
            entities_found=entities_found,
            total_redacted=len(results),
        )


def get_pii_scrubber(
    engine: str | None = None,
    strategy: MaskingStrategy | None = None,
) -> PIIScrubber | PresidioPIIScrubber:
    """Return the configured PII scrubber, falling back to regex when available.

    Args:
        engine: ``regex`` | ``presidio`` | ``auto``. Defaults to the ``pii_engine``
            setting.
        strategy: Masking strategy for the returned scrubber.
    """
    resolved = (engine or _configured_engine() or "auto").lower()

    if resolved in ("presidio", "auto"):
        try:
            return PresidioPIIScrubber(strategy or MaskingStrategy.REDACT)
        except Exception as exc:
            if resolved == "presidio":
                raise
            logger.info("Presidio unavailable (%s); using regex PII engine", exc)

    return PIIScrubber(strategy or MaskingStrategy.REDACT)


def _configured_engine() -> str | None:
    """Read ``pii_engine`` from settings without hard-failing on import."""
    try:
        from app.core.config import get_settings

        return get_settings().pii_engine
    except Exception:
        return None
