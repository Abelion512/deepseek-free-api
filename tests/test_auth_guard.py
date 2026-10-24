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

    def test_management_requires_key_regardless_of_client_ip(self, monkeypatch):
        # Uniform contract: client IP is never trusted (reverse-proxy safe).
        proxy = _load_proxy(monkeypatch, API_KEYS="alpha")
        for client in (("127.0.0.1", 5000), ("10.0.0.5", 5000)):
            # /api/* without a key: denied from ANY peer, loopback included.
            assert _guard_status(proxy, "/api/config", client=client) == 401
            # /api/* with a valid key: allowed from any peer.
            assert _guard_status(proxy, "/api/config", {"x-api-key": "alpha"}, client) == 200
            # The static admin form itself stays public (it prompts for the key).
            assert _guard_status(proxy, "/admin", client=client) == 200

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

    def test_wrong_key_rejected_everywhere(self, monkeypatch):
        proxy = _load_proxy(monkeypatch, API_KEYS="alpha")
        for path in ("/api/config", "/v1/models"):
            assert _guard_status(proxy, path, {"x-api-key": "wrong"}) == 401
            assert _guard_status(proxy, path, {"x-api-key": ""}) == 401
            assert _guard_status(proxy, path, {"authorization": "Bearer wrong"}) == 401

    def test_admin_page_key_wrapper_is_session_only_same_origin(self, monkeypatch):
        """The admin page must not put the key in the URL or persistent
        storage, and must only attach it to same-origin requests."""
        proxy = _load_proxy(monkeypatch, API_KEYS="alpha")
        body = proxy.ADMIN
        # Wrapper present: prompts once, in-memory variable only.
        assert "x-api-key" in body and "prompt(" in body
        # No key ingestion from the URL, no persistent storage.
        assert "location.search" not in body
        assert "localStorage" not in body
        assert "sessionStorage" not in body
        # Header attached exclusively to same-origin requests.
        assert ".origin===location.origin" in body

    def test_management_end_to_end_remote_client(self, monkeypatch):
        """Negative E2E as a remote client behind a same-host reverse proxy:
        the peer looks like a private IP, and /api must still 401 without a key."""
        pytest.importorskip("httpx")
        from fastapi.testclient import TestClient
        proxy = _load_proxy(monkeypatch, API_KEYS="alpha")
        remote = TestClient(proxy.app, client=("10.0.0.5", 5000))
        assert remote.get("/api/config").status_code == 401
        assert remote.get("/api/config", headers={"x-api-key": "alpha"}).status_code == 200
        assert remote.get("/admin").status_code == 200  # static form stays public
        assert remote.get("/health").status_code == 200
