"""OpenNotebook — Unit tests for the pluggable PII engine factory."""

from __future__ import annotations

import pytest

from app.domain.governance.pii import PIIScrubber
from app.domain.governance.pii_engine import get_pii_scrubber


def test_regex_engine_selected_explicitly():
    scrubber = get_pii_scrubber("regex")
    assert isinstance(scrubber, PIIScrubber)

    result = scrubber.scrub("Contact me at jane.doe@example.com please")
    assert "jane.doe@example.com" not in result.cleaned_text
    assert result.total_redacted >= 1


def test_auto_returns_a_working_scrubber():
    scrubber = get_pii_scrubber("auto")
    assert hasattr(scrubber, "scrub")
    result = scrubber.scrub("SSN 123-45-6789")
    assert result.cleaned_text is not None


def test_forced_presidio_raises_when_unavailable():
    try:
        import presidio_analyzer  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError):
            get_pii_scrubber("presidio")
    else:
        pytest.skip("Presidio is installed; forcing it should succeed instead")
