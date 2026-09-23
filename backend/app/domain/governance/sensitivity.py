"""OpenNotebook — Data Sensitivity Classification.

Defines enterprise data classification levels and clearance hierarchy.
"""

from __future__ import annotations

from enum import Enum


class SensitivityLevel(str, Enum):
    """Enterprise document sensitivity classification levels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

    @property
    def rank(self) -> int:
        """Numeric rank for clearance comparison."""
        ranks = {
            SensitivityLevel.PUBLIC: 1,
            SensitivityLevel.INTERNAL: 2,
            SensitivityLevel.CONFIDENTIAL: 3,
            SensitivityLevel.RESTRICTED: 4,
        }
        return ranks[self]

    def is_accessible_by(self, user_clearance: str | SensitivityLevel) -> bool:
        """Return True if user_clearance meets or exceeds this level."""
        if isinstance(user_clearance, str):
            try:
                user_clearance = SensitivityLevel(user_clearance.lower())
            except ValueError:
                return False
        return user_clearance.rank >= self.rank
