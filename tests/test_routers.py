from unittest.mock import AsyncMock, patch

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
# Interfaces
# ---------------------------------------------------------------------------


class TestListInterfaces:
    async def test_empty(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)):
            r = await client.get("/api/v1/interfaces")
            assert r.status_code == 200
            assert r.json() == []

    async def test_with_interfaces(self, client, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nAddress = 10.0.0.1/24\n")
        dump = f"wg0\tPRIVATE\t{VALID_KEY}\t51820\toff"
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=(dump, "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.get("/api/v1/interfaces")
            assert r.status_code == 200
            data = r.json()
            assert len(data) == 1
            assert data[0]["name"] == "wg0"
            assert data[0]["address"] == "10.0.0.1/24"


class TestCreateInterface:
    async def test_create_success(self, client, tmp_path):
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            get_dump = f"{VALID_KEY}\t{VALID_KEY}\t51820\toff"
            mock_run.side_effect = [
                ("", "", 0),  # wg-quick up
                (get_dump, "", 0),  # wg show dump
            ]
            r = await client.post(
                "/api/v1/interfaces",
                json={
                    "name": "wg0",
                    "address": "10.0.0.1/24",
                    "private_key": VALID_KEY,
                },
            )
            assert r.status_code == 201
            assert r.json()["name"] == "wg0"

    async def test_create_missing_private_key(self, client):
        r = await client.post("/api/v1/interfaces", json={"name": "wg0", "address": "10.0.0.1/24"})
        assert r.status_code == 400

    async def test_create_missing_address(self, client):
        r = await client.post("/api/v1/interfaces", json={"name": "wg0", "private_key": VALID_KEY})
        assert r.status_code == 400

    async def test_create_invalid_address(self, client):
        r = await client.post(
            "/api/v1/interfaces",
            json={"name": "wg0", "address": "bad", "private_key": VALID_KEY},
        )
        assert r.status_code == 422

    async def test_create_invalid_key(self, client):
        r = await client.post(
            "/api/v1/interfaces",
            json={"name": "wg0", "address": "10.0.0.1/24", "private_key": "bad"},
        )
        assert r.status_code == 422

    async def test_create_extra_field_rejected(self, client):
        r = await client.post(
            "/api/v1/interfaces",
            json={"name": "wg0", "address": "10.0.0.1/24", "private_key": VALID_KEY, "extra": "x"},
        )
        assert r.status_code == 422

    async def test_create_duplicate(self, client, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\n")
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            r = await client.post(
                "/api/v1/interfaces",
                json={"name": "wg0", "address": "10.0.0.1/24", "private_key": VALID_KEY},
            )
            assert r.status_code == 409


class TestGetInterface:
    async def test_found(self, client, tmp_path):
        dump = f"{VALID_KEY}\t{VALID_KEY}\t51820\toff"
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=(dump, "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.get("/api/v1/interfaces/wg0")
            assert r.status_code == 200
            assert r.json()["name"] == "wg0"

    async def test_not_found(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)):
            r = await client.get("/api/v1/interfaces/wg0")
            assert r.status_code == 404

    async def test_invalid_name(self, client):
        r = await client.get("/api/v1/interfaces/invalid@name")
        assert r.status_code == 422


class TestDeleteInterface:
    async def test_delete_success(self, client, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.delete("/api/v1/interfaces/wg0")
            assert r.status_code == 204
            assert not conf.exists()

    async def test_delete_not_found(self, client, tmp_path):
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            r = await client.delete("/api/v1/interfaces/wg0")
            assert r.status_code == 404

    async def test_delete_preserves_conf_on_failure(self, client, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "error", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.delete("/api/v1/interfaces/wg0")
            assert r.status_code == 400
            assert conf.exists()


class TestInterfaceActions:
    async def test_up(self, client, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.post("/api/v1/interfaces/wg0/up")
            assert r.status_code == 200
            assert r.json()["status"] == "up"

    async def test_down(self, client, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.post("/api/v1/interfaces/wg0/down")
            assert r.status_code == 200
            assert r.json()["status"] == "down"

    async def test_save(self, client, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.post("/api/v1/interfaces/wg0/save")
            assert r.status_code == 200
            assert r.json()["status"] == "saved"

    async def test_up_failure(self, client, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "fail", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.post("/api/v1/interfaces/wg0/up")
            assert r.status_code == 400

    async def test_up_not_found(self, client, tmp_path):
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            r = await client.post("/api/v1/interfaces/wg0/up")
            assert r.status_code == 404

    async def test_down_not_found(self, client, tmp_path):
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            r = await client.post("/api/v1/interfaces/wg0/down")
            assert r.status_code == 404

    async def test_save_not_found(self, client, tmp_path):
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            r = await client.post("/api/v1/interfaces/wg0/save")
            assert r.status_code == 404


# ---------------------------------------------------------------------------
# Peers
# ---------------------------------------------------------------------------


class TestListPeers:
    async def test_success(self, client):
        dump = f"PRIVATE\tPUBLIC\t51820\toff\n{VALID_KEY}\t(none)\t1.2.3.4:51820\t10.0.0.2/32\t0\t0\t0\toff"
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=(dump, "", 0)):
            r = await client.get("/api/v1/interfaces/wg0/peers")
            assert r.status_code == 200
            assert len(r.json()) == 1

    async def test_interface_not_found(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)):
            r = await client.get("/api/v1/interfaces/wg0/peers")
            assert r.status_code == 404


class TestCreatePeer:
    async def test_success(self, client):
        dump = f"PRIVATE\tPUBLIC\t51820\toff\n{VALID_KEY}\t(none)\t(none)\t10.0.0.2/32\t0\t0\t0\toff"
        with patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                ("", "", 0),  # wg set
                (dump, "", 0),  # wg show dump
            ]
            r = await client.post(
                "/api/v1/interfaces/wg0/peers",
                json={"public_key": VALID_KEY, "allowed_ips": "10.0.0.2/32"},
            )
            assert r.status_code == 201
            assert r.json()["public_key"] == VALID_KEY

    async def test_missing_allowed_ips(self, client):
        r = await client.post(
            "/api/v1/interfaces/wg0/peers",
            json={"public_key": VALID_KEY},
        )
        assert r.status_code == 422

    async def test_invalid_key(self, client):
        r = await client.post(
            "/api/v1/interfaces/wg0/peers",
            json={"public_key": "bad", "allowed_ips": "10.0.0.2/32"},
        )
        assert r.status_code == 422


class TestUpdatePeer:
    async def test_success(self, client):
        dump = f"PRIVATE\tPUBLIC\t51820\toff\n{VALID_KEY}\t(none)\t(none)\t10.0.0.3/32\t0\t0\t0\toff"
        with patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                ("", "", 0),  # wg set
                (dump, "", 0),  # wg show dump
            ]
            r = await client.put(
                f"/api/v1/interfaces/wg0/peers/{VALID_KEY}",
                json={"allowed_ips": "10.0.0.3/32"},
            )
            assert r.status_code == 200

    async def test_extra_field_rejected(self, client):
        r = await client.put(
            f"/api/v1/interfaces/wg0/peers/{VALID_KEY}",
            json={"allowed_ips": "10.0.0.3/32", "unknown": "x"},
        )
        assert r.status_code == 422


class TestDeletePeer:
    async def test_success(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)):
            r = await client.delete(f"/api/v1/interfaces/wg0/peers/{VALID_KEY}")
            assert r.status_code == 204
