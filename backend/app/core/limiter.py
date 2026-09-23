"""OpenNotebook — API Rate Limiter.

Provides a singleton Limiter instance based on client IP or user identity
to protect sensitive auth and inference endpoints from brute-force and DoS.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
)
