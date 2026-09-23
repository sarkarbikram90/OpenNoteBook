"""OpenNotebook — High-performance PII scrubber and redaction engine.

Detects and sanitizes:
- Social Security Numbers (SSN)
- Payment Card Numbers (with Luhn checksum validation)
- Email addresses
- Phone numbers (domestic & international)
- API Keys & Private Keys (AWS, GitHub, generic secrets)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum


class MaskingStrategy(str, Enum):
    """Masking method applied to detected PII."""

    REDACT = "redact"  # Replace with [REDACTED_<TYPE>]
    MASK = "mask"      # Partially obscure characters (e.g. ***-**-1234)
    HASH = "hash"      # Replace with SHA-256 digest


@dataclass
class PIIScrubResult:
    """Result of PII scrubbing pass."""

    cleaned_text: str
    entities_found: dict[str, int] = field(default_factory=dict)
    total_redacted: int = 0

    @property
    def has_pii(self) -> bool:
        """Return True if any PII entity was detected."""
        return self.total_redacted > 0


def _luhn_check(card_number: str) -> bool:
    """Validate credit card number using Luhn mod-10 algorithm."""
    digits = [int(d) for d in re.sub(r"\D", "", card_number)]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = d * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += d
    return checksum % 10 == 0


class PIIScrubber:
    """Configurable enterprise PII detection and redaction engine."""

    # Regex patterns
    SSN_PATTERN = re.compile(r"\b(?!000|666|9\d{2})\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b")
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
    CREDIT_CARD_CANDIDATE = re.compile(r"\b(?:\d{4}[- ]?){3}\d{1,4}\b|\b\d{13,19}\b")
    AWS_KEY_PATTERN = re.compile(r"\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b")
    GITHUB_TOKEN_PATTERN = re.compile(r"\b(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82})\b")
    PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC )?PRIVATE KEY-----")

    def __init__(self, default_strategy: MaskingStrategy = MaskingStrategy.REDACT) -> None:
        self.default_strategy = default_strategy

    def _mask_value(self, val: str, entity_type: str, strategy: MaskingStrategy) -> str:
        if strategy == MaskingStrategy.REDACT:
            return f"[REDACTED_{entity_type}]"
        elif strategy == MaskingStrategy.HASH:
            digest = hashlib.sha256(val.encode("utf-8")).hexdigest()[:12]
            return f"[HASH_{entity_type}_{digest}]"
        elif strategy == MaskingStrategy.MASK:
            digits_only = re.sub(r"\D", "", val)
            if entity_type == "CREDIT_CARD" and len(digits_only) >= 4:
                return f"****-****-****-{digits_only[-4:]}"
            if entity_type == "SSN" and len(digits_only) == 9:
                return f"***-**-{digits_only[-4:]}"
            if entity_type == "EMAIL" and "@" in val:
                user, domain = val.split("@", 1)
                return f"{user[:2]}***@{domain}"
            return f"[REDACTED_{entity_type}]"
        return f"[REDACTED_{entity_type}]"

    def scrub(self, text: str, strategy: MaskingStrategy | None = None) -> PIIScrubResult:
        """Sanitize text by replacing sensitive entities.

        Args:
            text: Raw input text.
            strategy: Masking strategy to use (default: instance default).

        Returns:
            PIIScrubResult containing sanitized text and detection metrics.
        """
        strat = strategy or self.default_strategy
        entities_found: dict[str, int] = {}
        total = 0
        cleaned = text

        # 1. Private Keys
        matches = self.PRIVATE_KEY_PATTERN.findall(cleaned)
        if matches:
            count = len(matches)
            entities_found["PRIVATE_KEY"] = count
            total += count
            cleaned = self.PRIVATE_KEY_PATTERN.sub(self._mask_value("key", "PRIVATE_KEY", strat), cleaned)

        # 2. AWS Keys
        matches = self.AWS_KEY_PATTERN.findall(cleaned)
        if matches:
            count = len(matches)
            entities_found["API_KEY"] = entities_found.get("API_KEY", 0) + count
            total += count
            cleaned = self.AWS_KEY_PATTERN.sub(self._mask_value("aws", "API_KEY", strat), cleaned)

        # 3. GitHub Tokens
        matches = self.GITHUB_TOKEN_PATTERN.findall(cleaned)
        if matches:
            count = len(matches)
            entities_found["API_KEY"] = entities_found.get("API_KEY", 0) + count
            total += count
            cleaned = self.GITHUB_TOKEN_PATTERN.sub(self._mask_value("gh", "API_KEY", strat), cleaned)

        # 4. SSN
        matches = self.SSN_PATTERN.findall(cleaned)
        if matches:
            count = len(matches)
            entities_found["SSN"] = count
            total += count
            cleaned = self.SSN_PATTERN.sub(self._mask_value("ssn", "SSN", strat), cleaned)

        # 5. Credit Cards (Luhn check validated)
        card_matches = self.CREDIT_CARD_CANDIDATE.findall(cleaned)
        card_count = 0
        for cand in card_matches:
            if _luhn_check(cand):
                card_count += 1
                cleaned = cleaned.replace(cand, self._mask_value(cand, "CREDIT_CARD", strat))
        if card_count > 0:
            entities_found["CREDIT_CARD"] = card_count
            total += card_count

        # 6. Emails
        email_matches = self.EMAIL_PATTERN.findall(cleaned)
        if email_matches:
            count = len(email_matches)
            entities_found["EMAIL"] = count
            total += count
            for m in set(email_matches):
                cleaned = cleaned.replace(m, self._mask_value(m, "EMAIL", strat))

        # 7. Phones
        phone_matches = self.PHONE_PATTERN.findall(cleaned)
        if phone_matches:
            valid_phones = [p for p in phone_matches if len(re.sub(r"\D", "", p)) >= 10]
            if valid_phones:
                count = len(valid_phones)
                entities_found["PHONE"] = count
                total += count
                for p in set(valid_phones):
                    cleaned = cleaned.replace(p, self._mask_value(p, "PHONE", strat))

        return PIIScrubResult(
            cleaned_text=cleaned,
            entities_found=entities_found,
            total_redacted=total,
        )
