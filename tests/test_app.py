from unittest.mock import AsyncMock, patch

import pytest
from httpx2 import ASGITransport, AsyncClient

from api.main import app
from tests import TEST_API_KEY
from tests.conftest import VALID_KEY

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestAuth:
    @pytest.fixture
    async def anonymous(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    async def test_rejects_missing_key(self, anonymous):
        r = await anonymous.get("/interfaces")
        assert r.status_code == 403

    @pytest.mark.parametrize("key", ["wrong", "", "test-api-key-012345678", "séc".encode("latin-1")])
    async def test_rejects_wrong_key(self, anonymous, key):
        r = await anonymous.get("/interfaces", headers={"X-API-Key": key})
        assert r.status_code == 403

    async def test_accepts_valid_key(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)):
            r = await client.get("/interfaces")
            assert r.status_code == 200

    async def test_health_does_not_need_a_key(self, anonymous):
        r = await anonymous.get("/health")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------


class TestExceptionHandlers:
    async def test_missing_wg_binary_returns_503(self, client):
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError(2, "No such file or directory")):
            r = await client.get("/interfaces/wg0")
            assert r.status_code == 503
            assert r.json()["detail"] == "Cannot execute wg: No such file or directory"

    async def test_wg_failure_returns_400_with_its_message(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "Line unrecognized", 1)):
            r = await client.delete(f"/interfaces/wg0/peers/{VALID_KEY}")
            assert r.status_code == 400
            assert r.json()["detail"] == "Line unrecognized"

    async def test_wg_failure_without_output_has_a_message(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 3)):
            r = await client.delete(f"/interfaces/wg0/peers/{VALID_KEY}")
            assert r.json()["detail"] == "wg exited with status 3"

    async def test_internal_value_error_is_not_a_client_error(self):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test", headers={"X-API-Key": TEST_API_KEY}) as c:
            with patch("api.services.wireguard._run", new_callable=AsyncMock, side_effect=ValueError("bug")):
                r = await c.get("/interfaces/wg0")
                assert r.status_code == 500
                assert r.json()["detail"] == "Internal server error"

    async def test_unhandled_exception_returns_500(self):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test", headers={"X-API-Key": TEST_API_KEY}) as c:
            with patch("api.services.wireguard._run", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
                r = await c.get("/interfaces")
                assert r.status_code == 500


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


class TestCORS:
    async def test_cors_allows_configured_origin(self, client):
        r = await client.options(
            "/health",
            headers={"Origin": "http://example.com", "Access-Control-Request-Method": "GET"},
        )
        assert r.headers.get("access-control-allow-origin") is not None

    async def test_cors_allows_api_key_header(self, client):
        r = await client.options(
            "/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )
        allow_headers = r.headers.get("access-control-allow-headers", "")
        assert "x-api-key" in allow_headers.lower()

    async def test_cors_wildcard_disables_credentials(self, client):
        r = await client.options(
            "/health",
            headers={"Origin": "http://example.com", "Access-Control-Request-Method": "GET"},
        )
        assert r.headers["access-control-allow-origin"] == "*"
        assert "access-control-allow-credentials" not in r.headers


# ---------------------------------------------------------------------------
# Root path
# ---------------------------------------------------------------------------


class TestRootPath:
    """Behind a proxy that publishes the API under /api/v1 and strips it, with UVICORN_ROOT_PATH=/api/v1."""

    @pytest.fixture
    async def proxied(self):
        transport = ASGITransport(app=app, root_path="/api/v1")
        async with AsyncClient(transport=transport, base_url="http://test", headers={"X-API-Key": TEST_API_KEY}) as ac:
            yield ac

    async def test_routes_answer_without_the_prefix(self, proxied):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)):
            r = await proxied.get("/interfaces")
            assert r.status_code == 200

    async def test_openapi_advertises_the_root_path(self, proxied):
        r = await proxied.get("/openapi.json")
        assert r.json()["servers"] == [{"url": "/api/v1"}]

    async def test_openapi_has_no_servers_without_a_root_path(self, client):
        r = await client.get("/openapi.json")
        assert "servers" not in r.json()
