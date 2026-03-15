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
