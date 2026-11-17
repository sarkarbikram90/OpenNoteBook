"""Vertex AI Text Embedding adapter for OpenNotebook.

Supports Vertex AI embedding models (e.g. ``text-embedding-004``) using
Application Default Credentials (ADC), with ``RETRIEVAL_DOCUMENT`` and
``RETRIEVAL_QUERY`` task types and configurable output dimensionality.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_adc_access_token() -> tuple[str, str | None]:
    """Acquire an OAuth2 bearer token and default project ID from ADC."""
    import google.auth
    from google.auth.transport.requests import Request

    credentials, default_project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    if not credentials.valid:
        credentials.refresh(Request())
    return str(credentials.token), default_project


def _predict_vertex_batch(
    texts: list[str],
    *,
    project_id: str,
    location: str,
    model_name: str,
    task_type: str,
    output_dimensionality: int,
    access_token: str,
    timeout_seconds: float = 30.0,
) -> list[list[float]]:
    """Call the Vertex AI publisher model ``:predict`` REST endpoint for one batch."""
    url = (
        f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}"
        f"/locations/{location}/publishers/google/models/{model_name}:predict"
    )
    instances: list[dict[str, Any]] = [
        {"content": text, "task_type": task_type} for text in texts
    ]
    payload: dict[str, Any] = {
        "instances": instances,
        "parameters": {"outputDimensionality": int(output_dimensionality)},
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()

    predictions = body.get("predictions") or []
    vectors: list[list[float]] = []
    for pred in predictions:
        emb_obj = pred.get("embeddings") if isinstance(pred, dict) else None
        values = emb_obj.get("values") if isinstance(emb_obj, dict) else None
        if not isinstance(values, list):
            raise RuntimeError("Vertex AI response missing embeddings.values")
        vectors.append([float(v) for v in values])

    if len(vectors) != len(texts):
        raise RuntimeError(
            f"Vertex AI returned {len(vectors)} embeddings for {len(texts)} inputs"
        )
    return vectors


def embed_texts_vertex_ai(
    texts: list[str],
    batch_size: int | None = None,
    is_query: bool = False,
) -> list[list[float]]:
    """Generate embeddings for ``texts`` using Vertex AI text embedding model.

    Args:
        texts: Input strings to embed.
        batch_size: Batch size per API call (Vertex AI supports up to 250;
            defaults to ``min(settings.embedding_batch_size, 100)``).
        is_query: Uses ``RETRIEVAL_QUERY`` when True, ``RETRIEVAL_DOCUMENT`` when False.

    Returns:
        List of float vectors matching ``settings.embedding_dimension``.
    """
    if not texts:
        return []

    settings = get_settings()
    effective_batch = min(batch_size or settings.embedding_batch_size, 100)
    task_type = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
    model_name = getattr(
        settings, "vertex_ai_embedding_model", "text-embedding-004"
    ).strip() or "text-embedding-004"
    location = getattr(settings, "vertex_ai_location", "us-central1").strip() or "us-central1"
    dimension = int(getattr(settings, "embedding_dimension", 384))

    access_token, adc_project = _get_adc_access_token()
    project_id = (
        getattr(settings, "gcs_project_id", "").strip()
        or (adc_project or "").strip()
    )
    if not project_id:
        raise RuntimeError(
            "GCS_PROJECT_ID (or ADC default project) must be configured when EMBEDDING_PROVIDER=vertex_ai"
        )

    start_time = time.perf_counter()
    all_vectors: list[list[float]] = []
    for idx in range(0, len(texts), effective_batch):
        batch = texts[idx : idx + effective_batch]
        batch_vectors = _predict_vertex_batch(
            batch,
            project_id=project_id,
            location=location,
            model_name=model_name,
            task_type=task_type,
            output_dimensionality=dimension,
            access_token=access_token,
        )
        all_vectors.extend(batch_vectors)

    duration = time.perf_counter() - start_time
    from app.core.metrics import embedding_duration

    embedding_duration.labels(
        batch_size=effective_batch,
        model=model_name,
    ).observe(duration)

    logger.info(
        "Generated %d Vertex AI embeddings (model=%s, task_type=%s, dim=%d)",
        len(all_vectors),
        model_name,
        task_type,
        len(all_vectors[0]) if all_vectors else 0,
    )
    return all_vectors
