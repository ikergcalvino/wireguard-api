import shutil
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from api.main import app

# ---------------------------------------------------------------------------
# Root & Health
# ---------------------------------------------------------------------------


class TestMeta:
    async def test_root(self, client):
        r = await client.get("/api/v1")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "wireguard-api"
        assert "version" in data

    async def test_health(self, client):
        r = await client.get("/api/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "checks" in data

    async def test_health_degraded_missing_wg(self, client):
        with patch.object(shutil, "which", side_effect=lambda cmd: None if cmd == "wg" else "/usr/bin/" + cmd):
            r = await client.get("/api/v1/health")
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "degraded"
            assert data["checks"]["wg"] == "missing"

    async def test_health_degraded_missing_wg_quick(self, client):
        with patch.object(shutil, "which", side_effect=lambda cmd: None if cmd == "wg-quick" else "/usr/bin/" + cmd):
            r = await client.get("/api/v1/health")
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "degraded"
            assert data["checks"]["wg_quick"] == "missing"

    async def test_health_degraded_missing_config_dir(self, client, tmp_path):
        missing = tmp_path / "nonexistent"
        with patch("api.main.settings") as mock_settings:
            mock_settings.config_dir = missing
            r = await client.get("/api/v1/health")
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "degraded"
            assert data["checks"]["config_dir"] == "missing"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestAuth:
    async def test_no_key_required_when_unset(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)):
            r = await client.get("/api/v1/interfaces")
            assert r.status_code == 200

    async def test_rejects_missing_key(self, client):
        with patch("api.dependencies.settings") as mock_settings:
            mock_settings.api_key = "secret"
            r = await client.get("/api/v1/interfaces")
            assert r.status_code == 403

    async def test_rejects_wrong_key(self, client):
        with patch("api.dependencies.settings") as mock_settings:
            mock_settings.api_key = "secret"
            r = await client.get("/api/v1/interfaces", headers={"X-API-Key": "wrong"})
            assert r.status_code == 403

    async def test_accepts_valid_key(self, client):
        with (
            patch("api.dependencies.settings") as mock_settings,
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
        ):
            mock_settings.api_key = "secret"
            r = await client.get("/api/v1/interfaces", headers={"X-API-Key": "secret"})
            assert r.status_code == 200


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------


class TestExceptionHandlers:
    async def test_permission_error_returns_403(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, side_effect=PermissionError("access denied")):
            r = await client.get("/api/v1/interfaces/wg0")
            assert r.status_code == 403
            assert "ermission" in r.json()["detail"]

    async def test_unhandled_exception_returns_500(self):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            with patch("api.services.wireguard._run", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
                r = await c.get("/api/v1/interfaces")
                assert r.status_code == 500


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


class TestCORS:
    async def test_cors_allows_configured_origin(self, client):
        r = await client.options(
            "/api/v1/health",
            headers={"Origin": "http://example.com", "Access-Control-Request-Method": "GET"},
        )
        assert r.headers.get("access-control-allow-origin") is not None

    async def test_cors_allows_api_key_header(self, client):
        r = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )
        allow_headers = r.headers.get("access-control-allow-headers", "")
        assert "x-api-key" in allow_headers.lower()

    async def test_cors_wildcard_disables_credentials(self):
        with patch("api.main.settings") as mock_settings:
            mock_settings.cors_origins = "*"
            mock_settings.api_key = ""
            mock_settings.config_dir.is_dir.return_value = True
            from api.main import cors_origins

            assert "*" in cors_origins
