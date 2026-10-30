import shutil
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from api.config import Settings, load_settings
from api.main import app
from tests import TEST_API_KEY
from tests.conftest import VALID_KEY

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
        with patch("api.routers.system.settings") as mock_settings:
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
    @pytest.fixture
    async def anonymous(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    async def test_rejects_missing_key(self, anonymous):
        r = await anonymous.get("/api/v1/interfaces")
        assert r.status_code == 403

    @pytest.mark.parametrize("key", ["wrong", "", "test-api-key-012345678", "séc".encode("latin-1")])
    async def test_rejects_wrong_key(self, anonymous, key):
        r = await anonymous.get("/api/v1/interfaces", headers={"X-API-Key": key})
        assert r.status_code == 403

    async def test_accepts_valid_key(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)):
            r = await client.get("/api/v1/interfaces")
            assert r.status_code == 200

    async def test_health_does_not_need_a_key(self, anonymous):
        r = await anonymous.get("/api/v1/health")
        assert r.status_code == 200


class TestSettings:
    def test_api_key_is_required(self, monkeypatch):
        monkeypatch.delenv("WG_API_KEY")
        with pytest.raises(ValidationError, match="api_key"):
            Settings()

    @pytest.mark.parametrize("key", ["", "short-key"])
    def test_api_key_must_be_long_enough(self, monkeypatch, key):
        monkeypatch.setenv("WG_API_KEY", key)
        with pytest.raises(ValidationError, match="at least 16 characters"):
            Settings()

    @pytest.mark.parametrize(("value", "expected"), [("debug", "DEBUG"), ("Warning", "WARNING"), ("ERROR", "ERROR")])
    def test_log_level_is_case_insensitive(self, monkeypatch, value, expected):
        monkeypatch.setenv("WG_LOG_LEVEL", value)
        assert Settings().log_level == expected

    def test_invalid_log_level_exits_with_a_readable_message(self, monkeypatch):
        monkeypatch.setenv("WG_LOG_LEVEL", "verbose")
        with pytest.raises(SystemExit, match="^Invalid configuration: WG_LOG_LEVEL: Input should be 'DEBUG'"):
            load_settings()

    def test_load_settings_exits_with_a_readable_message(self, monkeypatch):
        monkeypatch.delenv("WG_API_KEY")
        with pytest.raises(SystemExit, match="^Invalid configuration: WG_API_KEY: Field required$"):
            load_settings()


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------


class TestExceptionHandlers:
    async def test_missing_wg_binary_returns_503(self, client):
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError(2, "No such file or directory")):
            r = await client.get("/api/v1/interfaces/wg0")
            assert r.status_code == 503
            assert r.json()["detail"] == "Cannot execute wg: No such file or directory"

    async def test_wg_failure_returns_400_with_its_message(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "Line unrecognized", 1)):
            r = await client.delete(f"/api/v1/interfaces/wg0/peers/{VALID_KEY}")
            assert r.status_code == 400
            assert r.json()["detail"] == "Line unrecognized"

    async def test_wg_failure_without_output_has_a_message(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 3)):
            r = await client.delete(f"/api/v1/interfaces/wg0/peers/{VALID_KEY}")
            assert r.json()["detail"] == "wg exited with status 3"

    async def test_internal_value_error_is_not_a_client_error(self):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test", headers={"X-API-Key": TEST_API_KEY}) as c:
            with patch("api.services.wireguard._run", new_callable=AsyncMock, side_effect=ValueError("bug")):
                r = await c.get("/api/v1/interfaces/wg0")
                assert r.status_code == 500
                assert r.json()["detail"] == "Internal server error"

    async def test_unhandled_exception_returns_500(self):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test", headers={"X-API-Key": TEST_API_KEY}) as c:
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

    async def test_cors_wildcard_disables_credentials(self, client):
        r = await client.options(
            "/api/v1/health",
            headers={"Origin": "http://example.com", "Access-Control-Request-Method": "GET"},
        )
        assert r.headers["access-control-allow-origin"] == "*"
        assert "access-control-allow-credentials" not in r.headers

    def test_origin_list_is_comma_separated(self, monkeypatch):
        monkeypatch.setenv("WG_CORS_ORIGINS", "https://a.example, https://b.example")
        assert Settings().cors_origin_list == ["https://a.example", "https://b.example"]
