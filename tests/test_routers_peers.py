from unittest.mock import AsyncMock, patch

from tests.conftest import VALID_KEY

# ---------------------------------------------------------------------------
# List Peers
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


# ---------------------------------------------------------------------------
# Create Peer
# ---------------------------------------------------------------------------


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

    async def test_missing_public_key(self, client):
        r = await client.post(
            "/api/v1/interfaces/wg0/peers",
            json={"allowed_ips": "10.0.0.2/32"},
        )
        assert r.status_code == 422

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


# ---------------------------------------------------------------------------
# Get Peer
# ---------------------------------------------------------------------------


class TestGetPeer:
    async def test_success(self, client):
        dump = f"PRIVATE\tPUBLIC\t51820\toff\n{VALID_KEY}\t(none)\t1.2.3.4:51820\t10.0.0.2/32\t0\t0\t0\toff"
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=(dump, "", 0)):
            r = await client.get(f"/api/v1/interfaces/wg0/peers/{VALID_KEY}")
            assert r.status_code == 200
            assert r.json()["public_key"] == VALID_KEY

    async def test_not_found(self, client):
        dump = "PRIVATE\tPUBLIC\t51820\toff"
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=(dump, "", 0)):
            r = await client.get(f"/api/v1/interfaces/wg0/peers/{VALID_KEY}")
            assert r.status_code == 404

    async def test_interface_not_found(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)):
            r = await client.get(f"/api/v1/interfaces/wg0/peers/{VALID_KEY}")
            assert r.status_code == 404


# ---------------------------------------------------------------------------
# Update Peer
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Delete Peer
# ---------------------------------------------------------------------------


class TestDeletePeer:
    async def test_success(self, client):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)):
            r = await client.delete(f"/api/v1/interfaces/wg0/peers/{VALID_KEY}")
            assert r.status_code == 204
