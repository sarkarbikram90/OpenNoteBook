"""Unit tests for Cloud Run HTTP worker, fail-closed Pub/Sub auth, and dispatch tiers."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings


def test_settings_accepts_worker_http_config() -> None:
    """WORKER_HTTP_URL and WORKER_AUTH_TOKEN load cleanly into Settings."""
    settings = Settings(
        worker_http_url="https://opennotebook-worker-abc.a.run.app",
        worker_auth_token="secret-worker-token-1234",
    )
    assert settings.worker_http_url == "https://opennotebook-worker-abc.a.run.app"
    assert settings.worker_auth_token == "secret-worker-token-1234"


def test_pubsub_token_fails_closed_in_production() -> None:
    """In production, missing PUBSUB_VERIFICATION_TOKEN must fail closed (HTTP 503)."""
    fastapi = pytest.importorskip("fastapi")
    from app.api.v1.events import _verify_pubsub_token

    with pytest.raises(fastapi.HTTPException) as exc_info:
        _verify_pubsub_token("", None, None, app_env="production")
    assert exc_info.value.status_code == 503

    # Development allows empty token for local testing
    _verify_pubsub_token("", None, None, app_env="development")

    # Wrong token is rejected with 403
    with pytest.raises(fastapi.HTTPException) as exc_info:
        _verify_pubsub_token("expected-secret", "wrong-secret", None, app_env="production")
    assert exc_info.value.status_code == 403

    # Matching query or Bearer token succeeds
    _verify_pubsub_token("expected-secret", "expected-secret", None, app_env="production")
    _verify_pubsub_token("expected-secret", None, "Bearer expected-secret", app_env="production")


def test_worker_token_verification_and_http_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify http_worker token guard and HTTP worker fallback dispatch."""
    fastapi = pytest.importorskip("fastapi")
    from app.api.v1 import sources as sources_api
    from app.worker.http_worker import verify_worker_token

    with pytest.raises(fastapi.HTTPException) as exc_info:
        verify_worker_token("", app_env="production")
    assert exc_info.value.status_code == 503

    verify_worker_token("tok-123", header_token="tok-123", app_env="production")

    with pytest.raises(fastapi.HTTPException) as exc_info:
        verify_worker_token("tok-123", header_token="bad", app_env="production")
    assert exc_info.value.status_code == 403

    # Exercise _post_to_http_worker with mocked httpx
    called: list[tuple[str, dict[str, str]]] = []

    class _FakeResp:
        def raise_for_status(self) -> None:
            return None

    fake_settings = SimpleNamespace(
        worker_http_url="https://worker.internal.run.app/",
        worker_auth_token="shared-secret",
        pubsub_verification_token="",
    )
    monkeypatch.setattr(sources_api, "get_settings", lambda: fake_settings)

    import httpx

    def _fake_post(url: str, headers: dict[str, str], timeout: float) -> Any:
        called.append((url, headers))
        return _FakeResp()

    monkeypatch.setattr(httpx, "post", _fake_post)

    src_id = uuid.uuid4()
    ok = sources_api._post_to_http_worker(f"/tasks/process-source/{src_id}", src_id)
    assert ok is True
    assert called == [
        (
            f"https://worker.internal.run.app/tasks/process-source/{src_id}",
            {"X-Worker-Token": "shared-secret"},
        )
    ]
