import shutil
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Info & Health
# ---------------------------------------------------------------------------


class TestSystem:
    async def test_info(self, client):
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
