"""OpenNotebook — Shared helpers for connectors."""

from __future__ import annotations

import json
from typing import Any


def parse_acl(value: Any) -> list[str]:
    """Parse an ACL cell that may be a list, a JSON array string, or CSV.

    Examples:
        '["a","b"]' -> ["a", "b"]
        "a, b, c"   -> ["a", "b", "c"]
        ["x", "y"]  -> ["x", "y"]
        None        -> []
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if v]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(v) for v in parsed if v]
            except json.JSONDecodeError:
                pass
        return [part.strip() for part in text.split(",") if part.strip()]
    return [str(value)]
