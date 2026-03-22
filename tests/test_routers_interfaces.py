from unittest.mock import AsyncMock, patch

from tests.conftest import VALID_KEY

# ---------------------------------------------------------------------------
# List Interfaces
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
            assert data[0]["status"] == "up"


# ---------------------------------------------------------------------------
# Create Interface
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Update Interface
# ---------------------------------------------------------------------------


class TestUpdateInterface:
    async def test_update_success(self, client, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nAddress = 10.0.0.1/24\nPrivateKey = old\n")
        get_dump = f"{VALID_KEY}\t{VALID_KEY}\t51820\toff"
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            mock_run.side_effect = [
                ("PRIVATE\tPUBLIC\t51820\toff", "", 0),  # wg show dump (list_peers)
                ("PRIVATE\tPUBLIC\t51820\toff", "", 0),  # wg show dump (check if up)
                ("", "", 0),  # wg syncconf
                (get_dump, "", 0),  # wg show dump (get_interface)
            ]
            r = await client.put(
                "/api/v1/interfaces/wg0",
                json={"name": "wg0", "address": "10.0.0.2/24", "private_key": VALID_KEY},
            )
            assert r.status_code == 200
            assert r.json()["name"] == "wg0"
            content = conf.read_text()
            assert "10.0.0.2/24" in content

    async def test_update_not_found(self, client, tmp_path):
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            r = await client.put(
                "/api/v1/interfaces/wg0",
                json={"name": "wg0", "address": "10.0.0.1/24", "private_key": VALID_KEY},
            )
            assert r.status_code == 404

    async def test_update_missing_private_key(self, client, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\n")
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            r = await client.put(
                "/api/v1/interfaces/wg0",
                json={"name": "wg0", "address": "10.0.0.1/24"},
            )
            assert r.status_code == 400

    async def test_update_missing_address(self, client, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\n")
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            r = await client.put(
                "/api/v1/interfaces/wg0",
                json={"name": "wg0", "private_key": VALID_KEY},
            )
            assert r.status_code == 400

    async def test_update_name_mismatch(self, client):
        r = await client.put(
            "/api/v1/interfaces/wg0",
            json={"name": "wg1", "address": "10.0.0.1/24", "private_key": VALID_KEY},
        )
        assert r.status_code == 422
        assert "name" in r.json()["detail"].lower()

    async def test_update_syncconf_failure(self, client, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\nAddress = 10.0.0.1/24\nPrivateKey = old\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            mock_run.side_effect = [
                ("PRIVATE\tPUBLIC\t51820\toff", "", 0),  # wg show dump (list_peers)
                ("PRIVATE\tPUBLIC\t51820\toff", "", 0),  # wg show dump (check if up)
                ("", "syncconf failed", 1),  # wg syncconf
            ]
            r = await client.put(
                "/api/v1/interfaces/wg0",
                json={"name": "wg0", "address": "10.0.0.2/24", "private_key": VALID_KEY},
            )
            assert r.status_code == 400

    async def test_update_success_but_get_returns_none(self, client):
        with (
            patch("api.routers.interfaces.wg.update_interface", new_callable=AsyncMock, return_value=("", 0)),
            patch("api.routers.interfaces.wg.get_interface", new_callable=AsyncMock, return_value=None),
        ):
            r = await client.put(
                "/api/v1/interfaces/wg0",
                json={"name": "wg0", "address": "10.0.0.2/24", "private_key": VALID_KEY},
            )
            assert r.status_code == 500
            assert "could not be retrieved" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Get Interface
# ---------------------------------------------------------------------------


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

    async def test_not_found(self, client, tmp_path):
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.get("/api/v1/interfaces/wg0")
            assert r.status_code == 404

    async def test_invalid_name(self, client):
        r = await client.get("/api/v1/interfaces/invalid@name")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Delete Interface
# ---------------------------------------------------------------------------


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

    async def test_delete_down_interface(self, client, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nAddress = 10.0.0.1/24\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            mock_run.side_effect = [
                ("", "not running", 1),  # wg-quick down fails
                ("", "err", 1),  # wg show dump — not running
            ]
            r = await client.delete("/api/v1/interfaces/wg0")
            assert r.status_code == 204
            assert not conf.exists()

    async def test_delete_fails_when_up_but_down_errors(self, client, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            mock_run.side_effect = [
                ("", "some error", 1),  # wg-quick down fails
                ("PRIVATE\tPUBLIC\t51820\toff", "", 0),  # wg show — still running
            ]
            r = await client.delete("/api/v1/interfaces/wg0")
            assert r.status_code == 400
            assert conf.exists()


# ---------------------------------------------------------------------------
# Interface Actions (up / down / save)
# ---------------------------------------------------------------------------


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
