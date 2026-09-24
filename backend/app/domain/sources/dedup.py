"""OpenNotebook — Source deduplication by checksum.

Ingestion is made idempotent by comparing the SHA-256 checksum of an incoming
document against checksums already recorded for the same notebook. Duplicates
(including connector re-syncs) are skipped instead of creating new Source rows
and re-embedding the same content.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.infrastructure.db.models import Source

logger = logging.getLogger(__name__)


def checksum_exists(existing_checksums: Iterable[str], target: str) -> bool:
    """Pure helper: return True if ``target`` is already among existing checksums."""
    return target in set(existing_checksums)


async def find_source_by_checksum(
    db: AsyncSession,
    notebook_id: uuid.UUID,
    checksum: str,
    exclude_failed: bool = True,
) -> Source | None:
    """Return an existing source in the notebook with the given checksum.

    Args:
        db: Active async database session.
        notebook_id: Notebook to scope the search to.
        checksum: SHA-256 checksum of the incoming document.
        exclude_failed: When True, ignore FAILED sources so they can be retried.

    Returns:
        The earliest matching ``Source``, or None if no duplicate exists.
    """
    from sqlalchemy import select

    from app.infrastructure.db.models import Source

    stmt = (
        select(Source)
        .where(Source.notebook_id == notebook_id, Source.checksum == checksum)
        .order_by(Source.created_at.asc())
        .limit(1)
    )
    if exclude_failed:
        stmt = stmt.where(Source.status != "FAILED")

    result = await db.execute(stmt)
    return result.scalar_one_or_none()
