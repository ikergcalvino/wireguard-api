from unittest.mock import AsyncMock, patch

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
