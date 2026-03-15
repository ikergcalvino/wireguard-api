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

    async def test_returns_none_when_down_no_conf(self, tmp_path):
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            assert await list_peers("wg0") is None

    async def test_returns_peers_from_conf_when_down(self, tmp_path):
        (tmp_path / "wg0.conf").write_text(
            f"[Interface]\nAddress = 10.0.0.1/24\n\n[Peer]\nPublicKey = {VALID_KEY}\nAllowedIPs = 10.0.0.2/32\n"
        )
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            peers = await list_peers("wg0")
            assert peers is not None
            assert len(peers) == 1
            assert peers[0].public_key == VALID_KEY


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

    async def test_returns_none_on_error(self, tmp_path):
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            assert await get_peer("wg0", VALID_KEY) is None


# ---------------------------------------------------------------------------
# set_peer
# ---------------------------------------------------------------------------


class TestSetPeer:
    async def test_success(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)):
            stderr, rc, saved = await set_peer("wg0", VALID_KEY, allowed_ips="10.0.0.2/32")
            assert rc == 0
            assert saved is True

    async def test_auto_saves_after_success(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)) as mock_run:
            await set_peer("wg0", VALID_KEY, allowed_ips="10.0.0.2/32")
            assert mock_run.call_count == 2
            save_args = mock_run.call_args_list[1][0][0]
            assert save_args == ["wg-quick", "save", "wg0"]

    async def test_reports_save_failure(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                ("", "", 0),  # wg set ok
                ("", "save error", 1),  # wg-quick save fails
            ]
            stderr, rc, saved = await set_peer("wg0", VALID_KEY, allowed_ips="10.0.0.2/32")
            assert rc == 0
            assert saved is False

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
            args = mock_run.call_args_list[0][0][0]
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
            stderr, rc, saved = await delete_peer("wg0", VALID_KEY)
            assert rc == 0
            assert saved is True
            args = mock_run.call_args_list[0][0][0]
            assert "remove" in args

    async def test_auto_saves_after_success(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)) as mock_run:
            await delete_peer("wg0", VALID_KEY)
            assert mock_run.call_count == 2
            save_args = mock_run.call_args_list[1][0][0]
            assert save_args == ["wg-quick", "save", "wg0"]

    async def test_no_save_on_failure(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "error", 1)) as mock_run:
            stderr, rc, saved = await delete_peer("wg0", VALID_KEY)
            assert rc == 1
            assert saved is False
            assert mock_run.call_count == 1

    async def test_reports_save_failure(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                ("", "", 0),  # wg set remove ok
                ("", "save error", 1),  # wg-quick save fails
            ]
            stderr, rc, saved = await delete_peer("wg0", VALID_KEY)
            assert rc == 0
            assert saved is False
