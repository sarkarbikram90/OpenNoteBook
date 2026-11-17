"""Google Gemini Vision & Document AI OCR adapters for image extraction.

Provides:
1. ``extract_image_with_gemini_vision`` — extracts visible text AND semantic
   diagram/chart descriptions using Gemini multimodal vision.
2. ``extract_image_with_document_ai`` — extracts structured OCR text using
   Google Cloud Document AI processor REST API with ADC credentials.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_VISION_PROMPT = (
    "Extract all visible text from this image verbatim, preserving headings, "
    "labels, and table structures. If the image contains diagrams, charts, or "
    "architectural flows, append a concise 'Visual Summary:' section describing "
    "the components and relationships shown."
)


def extract_image_with_gemini_vision(
    image_bytes: bytes,
    mime_type: str = "image/png",
    timeout_seconds: float = 30.0,
) -> str:
    """Use Gemini Vision API to transcribe text and describe visual elements."""
    settings = get_settings()
    api_key = getattr(settings, "gemini_api_key", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY must be configured when IMAGE_VISION_PROVIDER=gemini"
        )

    base_url = getattr(
        settings, "gemini_base_url", "https://generativelanguage.googleapis.com"
    ).rstrip("/")
    model = getattr(settings, "gemini_model", "gemini-1.5-flash").strip() or "gemini-1.5-flash"
    url = f"{base_url}/v1beta/models/{model}:generateContent"

    encoded = base64.b64encode(image_bytes).decode("ascii")
    payload: dict[str, Any] = {
        "contents": [
            {
                "parts": [
                    {"text": _VISION_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": encoded,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {"temperature": 0.0},
    }

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(url, params={"key": api_key}, json=payload)
        response.raise_for_status()
        body = response.json()

    candidates = body.get("candidates") or []
    parts_text: list[str] = []
    for cand in candidates:
        content = cand.get("content") if isinstance(cand, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts_text.append(part["text"].strip())

    return "\n\n".join(p for p in parts_text if p).strip()


def extract_image_with_document_ai(
    image_bytes: bytes,
    mime_type: str = "image/png",
    timeout_seconds: float = 30.0,
) -> str:
    """Use Google Cloud Document AI ``:process`` endpoint with ADC credentials."""
    from app.infrastructure.embeddings.vertex_ai import _get_adc_access_token

    settings = get_settings()
    processor_name = getattr(settings, "document_ai_processor_name", "").strip()
    if not processor_name:
        raise RuntimeError(
            "DOCUMENT_AI_PROCESSOR_NAME must be configured when IMAGE_VISION_PROVIDER=document_ai"
        )

    access_token, _ = _get_adc_access_token()
    # processor_name format: projects/{project}/locations/{location}/processors/{id}
    parts = processor_name.strip("/").split("/")
    location = "us"
    if "locations" in parts:
        loc_idx = parts.index("locations")
        if loc_idx + 1 < len(parts):
            location = parts[loc_idx + 1]

    url = f"https://{location}-documentai.googleapis.com/v1/{processor_name.strip('/')}:process"
    payload = {
        "rawDocument": {
            "content": base64.b64encode(image_bytes).decode("ascii"),
            "mimeType": mime_type,
        }
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()

    document = body.get("document") if isinstance(body, dict) else None
    text = document.get("text") if isinstance(document, dict) else ""
    return str(text or "").strip()
