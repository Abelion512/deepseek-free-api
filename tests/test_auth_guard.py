"""Tests for the fail-closed client-auth guard in proxy.py.

Run: pip install pytest httpx  (httpx only for the TestClient integration test)
     python -m pytest tests/test_auth_guard.py -v
"""
import asyncio
import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _load_proxy(monkeypatch, **env):
    """(Re)import proxy.py with a controlled environment."""
    for key in ("PROXY_HOST", "PROXY_PORT", "API_KEYS"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import proxy
    return importlib.reload(proxy)


def _make_request(path, headers=None, client=("127.0.0.1", 5000)):
    from starlette.requests import Request
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": raw,
        "client": client,
        "query_string": b"",
    }
    return Request(scope)


async def _noop_call_next(request):
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": True})


def _guard_status(proxy, path, headers=None, client=("127.0.0.1", 5000)):
    resp = asyncio.run(
        proxy.client_auth_guard(_make_request(path, headers, client), _noop_call_next)
    )
    return resp.status_code


class TestValidateBind:
    def test_loopback_without_keys_allowed(self, monkeypatch):
        proxy = _load_proxy(monkeypatch)
        proxy._validate_bind("127.0.0.1")  # must not raise

    def test_non_loopback_without_keys_refuses(self, monkeypatch):
        proxy = _load_proxy(monkeypatch)
        with pytest.raises(SystemExit):
            proxy._validate_bind("0.0.0.0")

    def test_non_loopback_with_keys_allowed(self, monkeypatch):
        proxy = _load_proxy(monkeypatch, API_KEYS="k1")
        proxy._validate_bind("0.0.0.0")  # must not raise

    def test_default_host_is_loopback(self, monkeypatch):
        proxy = _load_proxy(monkeypatch)
        assert proxy.PROXY_HOST == "127.0.0.1"


class TestClientAuthGuard:
    def test_no_keys_local_mode_unchanged(self, monkeypatch):
        proxy = _load_proxy(monkeypatch)
        assert _guard_status(proxy, "/v1/models") == 200
        assert _guard_status(proxy, "/admin") == 200

    def test_v1_requires_key_when_configured(self, monkeypatch):
        proxy = _load_proxy(monkeypatch, API_KEYS="alpha, beta")
        assert _guard_status(proxy, "/v1/models") == 401
        assert _guard_status(proxy, "/v1/models", {"x-api-key": "wrong"}) == 401
        assert _guard_status(proxy, "/v1/models", {"x-api-key": "alpha"}) == 200
        assert _guard_status(proxy, "/v1/chat/completions", {"Authorization": "Bearer beta"}) == 200

    def test_management_loopback_only_when_keys_configured(self, monkeypatch):
        proxy = _load_proxy(monkeypatch, API_KEYS="alpha")
        # Loopback management traffic keeps working (admin browser UX).
        assert _guard_status(proxy, "/admin", client=("127.0.0.1", 5000)) == 200
        assert _guard_status(proxy, "/api/config", client=("::1", 5000)) == 200
        # Remote management traffic is denied even with no /v1 involved.
        assert _guard_status(proxy, "/admin", client=("10.0.0.5", 5000)) == 403
        assert _guard_status(proxy, "/api/config", client=("10.0.0.5", 5000)) == 403

    def test_health_stays_public(self, monkeypatch):
        proxy = _load_proxy(monkeypatch, API_KEYS="alpha")
        assert _guard_status(proxy, "/health", client=("10.0.0.5", 5000)) == 200


class TestIntegration:
    """Full FastAPI wiring check via TestClient (needs httpx)."""

    def test_v1_models_end_to_end(self, monkeypatch):
        pytest.importorskip("httpx")
        from fastapi.testclient import TestClient
        proxy = _load_proxy(monkeypatch, API_KEYS="alpha")
        client = TestClient(proxy.app)
        assert client.get("/v1/models").status_code == 401
        assert client.get("/v1/models", headers={"x-api-key": "alpha"}).status_code == 200
