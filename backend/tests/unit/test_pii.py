"""OpenNotebook — Unit tests for enterprise PII detection and redaction."""

from __future__ import annotations

import pytest

from app.domain.governance.pii import MaskingStrategy, PIIScrubber, _luhn_check


def test_luhn_algorithm_check():
    """Verify Luhn mod-10 validation on standard card numbers and bogus strings."""
    # Standard valid test card numbers (Visa, Mastercard test numbers)
    assert _luhn_check("4532015112830366") is True
    # Inverted or corrupted card number
    assert _luhn_check("4532015112830367") is False
    # Short string
    assert _luhn_check("12345") is False


def test_pii_scrubber_ssn_redaction():
    """Verify SSN detection and redaction."""
    scrubber = PIIScrubber(default_strategy=MaskingStrategy.REDACT)
    text = "The employee SSN is 123-45-6789 and must be safeguarded."
    result = scrubber.scrub(text)

    assert result.has_pii is True
    assert result.total_redacted == 1
    assert result.entities_found["SSN"] == 1
    assert "123-45-6789" not in result.cleaned_text
    assert "[REDACTED_SSN]" in result.cleaned_text


def test_pii_scrubber_credit_card_masking():
    """Verify credit card detection with partial masking strategy."""
    scrubber = PIIScrubber(default_strategy=MaskingStrategy.MASK)
    # Valid test card number
    text = "Charge payment to card 4532-0151-1283-0366 today."
    result = scrubber.scrub(text)

    assert result.has_pii is True
    assert result.entities_found["CREDIT_CARD"] == 1
    assert "****-****-****-0366" in result.cleaned_text
    assert "4532" not in result.cleaned_text


def test_pii_scrubber_email_and_phone():
    """Verify emails and phone numbers are scrubbed."""
    scrubber = PIIScrubber(default_strategy=MaskingStrategy.REDACT)
    text = "Contact Jane Doe at jane.doe@enterprise.com or call +1 (555) 234-5678."
    result = scrubber.scrub(text)

    assert result.has_pii is True
    assert result.entities_found["EMAIL"] == 1
    assert result.entities_found["PHONE"] == 1
    assert "jane.doe@enterprise.com" not in result.cleaned_text
    assert "[REDACTED_EMAIL]" in result.cleaned_text
    assert "[REDACTED_PHONE]" in result.cleaned_text


def test_pii_scrubber_api_keys():
    """Verify AWS access keys and GitHub tokens are redacted."""
    scrubber = PIIScrubber(default_strategy=MaskingStrategy.REDACT)
    text = "Deploy with AWS_KEY=AKIAIOSFODNN7EXAMPLE and GH=ghp_1234567890abcdefghijklmnopqrstuvwxyz."
    result = scrubber.scrub(text)

    assert result.has_pii is True
    assert result.entities_found["API_KEY"] == 2
    assert "AKIAIOSFODNN7EXAMPLE" not in result.cleaned_text
    assert "[REDACTED_API_KEY]" in result.cleaned_text


def test_pii_scrubber_clean_text():
    """Verify text with no sensitive data passes unchanged."""
    scrubber = PIIScrubber()
    text = "This is a public quarterly company overview outlining product strategy and roadmap."
    result = scrubber.scrub(text)

    assert result.has_pii is False
    assert result.total_redacted == 0
    assert result.cleaned_text == text
