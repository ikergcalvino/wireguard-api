from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import VALID_KEY

# ---------------------------------------------------------------------------
# List Interfaces
# ---------------------------------------------------------------------------


class TestListInterfaces:
    async def test_empty(self, client, tmp_path):
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.get("/interfaces")
            assert r.status_code == 200
            assert r.json() == []

    async def test_with_interfaces(self, client, tmp_path):
        (tmp_path / "wg1.conf").write_text("")
        dump = f"wg0\tPRIVATE\t{VALID_KEY}\t51820\toff"
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=(dump, "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.get("/interfaces")
            assert r.status_code == 200
            data = r.json()
            assert [(i["name"], i["status"]) for i in data] == [("wg0", "up"), ("wg1", "down")]
            assert data[0]["listen_port"] == 51820


# ---------------------------------------------------------------------------
# Get Interface
# ---------------------------------------------------------------------------


class TestGetInterface:
    async def test_found(self, client, tmp_path):
        dump = f"PRIVATE\t{VALID_KEY}\t51820\toff"
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=(dump, "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.get("/interfaces/wg0")
            assert r.status_code == 200
            assert r.json()["name"] == "wg0"
            assert r.json()["status"] == "up"
            assert "private_key" not in r.json()

    async def test_down(self, client, tmp_path):
        (tmp_path / "wg0.conf").write_text("")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.get("/interfaces/wg0")
            assert r.status_code == 200
            assert r.json()["status"] == "down"

    async def test_not_found(self, client, tmp_path):
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.get("/interfaces/wg0")
            assert r.status_code == 404

    async def test_invalid_name(self, client):
        r = await client.get("/interfaces/invalid@name")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Update Interface
# ---------------------------------------------------------------------------


class TestUpdateInterface:
    async def test_success(self, client):
        dump = f"PRIVATE\t{VALID_KEY}\t51821\toff"
        with patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                ("", "", 0),  # wg set
                (dump, "", 0),  # wg show dump (get_interface)
            ]
            r = await client.patch("/interfaces/wg0", json={"listen_port": 51821})
            assert r.status_code == 200
            assert r.json()["listen_port"] == 51821

    async def test_wg_failure(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "No such device", 1)):
            r = await client.patch("/interfaces/wg0", json={"listen_port": 51821})
            assert r.status_code == 400
            assert r.json()["detail"] == "No such device"

    @pytest.mark.parametrize(
        "body",
        [
            {"private_key": "bad"},
            {"listen_port": 0},
            {"fw_mark": "0x1\nPostUp = id"},
            {"address": "10.0.0.1/24"},
        ],
    )
    async def test_invalid_body(self, client, body):
        r = await client.patch("/interfaces/wg0", json=body)
        assert r.status_code == 422

    async def test_put_not_allowed(self, client):
        r = await client.put("/interfaces/wg0", json={"listen_port": 51821})
        assert r.status_code == 405

    async def test_success_but_get_returns_none(self, client):
        with (
            patch("api.routers.interfaces.wg.update_interface", new_callable=AsyncMock, return_value=("", 0)),
            patch("api.routers.interfaces.wg.get_interface", new_callable=AsyncMock, return_value=None),
        ):
            r = await client.patch("/interfaces/wg0", json={"listen_port": 51821})
            assert r.status_code == 500
            assert "could not be retrieved" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Removed endpoints
# ---------------------------------------------------------------------------


class TestNoFileManagement:
    async def test_create_not_available(self, client):
        r = await client.post("/interfaces", json={"name": "wg0"})
        assert r.status_code == 405

    async def test_delete_not_available(self, client):
        r = await client.delete("/interfaces/wg0")
        assert r.status_code == 405


# ---------------------------------------------------------------------------
# Interface Actions (up / down / save)
# ---------------------------------------------------------------------------


class TestInterfaceActions:
    @pytest.mark.parametrize(("action", "status"), [("up", "up"), ("down", "down"), ("save", "saved")])
    async def test_success(self, client, tmp_path, action, status):
        (tmp_path / "wg0.conf").write_text("")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.post(f"/interfaces/wg0/{action}")
            assert r.status_code == 200
            assert r.json() == {"status": status, "interface": "wg0"}

    @pytest.mark.parametrize("action", ["up", "down", "save"])
    async def test_failure(self, client, tmp_path, action):
        (tmp_path / "wg0.conf").write_text("")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "fail", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            r = await client.post(f"/interfaces/wg0/{action}")
            assert r.status_code == 400

    @pytest.mark.parametrize("action", ["up", "down", "save"])
    async def test_not_found(self, client, tmp_path, action):
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            r = await client.post(f"/interfaces/wg0/{action}")
            assert r.status_code == 404
