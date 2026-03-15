from unittest.mock import AsyncMock, patch

import pytest

from api.services.wireguard import (
    delete_peer,
    get_peer,
    list_peers,
    set_peer,
)
from tests.conftest import VALID_KEY

# ---------------------------------------------------------------------------
# list_peers
# ---------------------------------------------------------------------------


class TestListPeers:
    async def test_returns_peers(self):
        dump = f"PRIVATE\tPUBLIC\t51820\toff\n{VALID_KEY}\t(none)\t1.2.3.4:51820\t10.0.0.2/32\t0\t0\t0\toff"
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=(dump, "", 0)):
            peers = await list_peers("wg0")
            assert peers is not None
            assert len(peers) == 1

    async def test_returns_none_on_error(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)):
            assert await list_peers("wg0") is None


# ---------------------------------------------------------------------------
# get_peer
# ---------------------------------------------------------------------------


class TestGetPeer:
    async def test_returns_peer(self):
        dump = f"PRIVATE\tPUBLIC\t51820\toff\n{VALID_KEY}\t(none)\t1.2.3.4:51820\t10.0.0.2/32\t0\t0\t0\toff"
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=(dump, "", 0)):
            peer = await get_peer("wg0", VALID_KEY)
            assert peer is not None
            assert peer.public_key == VALID_KEY

    async def test_returns_none_when_not_found(self):
        dump = "PRIVATE\tPUBLIC\t51820\toff"
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=(dump, "", 0)):
            assert await get_peer("wg0", VALID_KEY) is None

    async def test_returns_none_on_error(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)):
            assert await get_peer("wg0", VALID_KEY) is None


# ---------------------------------------------------------------------------
# set_peer
# ---------------------------------------------------------------------------


class TestSetPeer:
    async def test_success(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)):
            stderr, rc = await set_peer("wg0", VALID_KEY, allowed_ips="10.0.0.2/32")
            assert rc == 0

    async def test_with_all_options(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)) as mock_run:
            await set_peer(
                "wg0",
                VALID_KEY,
                allowed_ips="10.0.0.2/32",
                endpoint="1.2.3.4:51820",
                preshared_key="psk-data",
                persistent_keepalive=25,
            )
            args = mock_run.call_args[0][0]
            assert "allowed-ips" in args
            assert "endpoint" in args
            assert "preshared-key" in args
            assert "persistent-keepalive" in args

    async def test_missing_public_key(self):
        with pytest.raises(ValueError, match="public_key"):
            await set_peer("wg0", "")


# ---------------------------------------------------------------------------
# delete_peer
# ---------------------------------------------------------------------------


class TestDeletePeer:
    async def test_success(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)) as mock_run:
            stderr, rc = await delete_peer("wg0", VALID_KEY)
            assert rc == 0
            args = mock_run.call_args[0][0]
            assert "remove" in args

    async def test_failure(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "error", 1)):
            stderr, rc = await delete_peer("wg0", VALID_KEY)
            assert rc == 1
