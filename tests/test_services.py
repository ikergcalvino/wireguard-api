from unittest.mock import AsyncMock, patch

import pytest

from api.services.wireguard import (
    _conf_path,
    _parse_peers_dump,
    _read_conf_address,
    _run,
    get_interface,
    list_interfaces,
    list_peers,
)
from tests.conftest import VALID_KEY

# ---------------------------------------------------------------------------
# _run
# ---------------------------------------------------------------------------


class TestRun:
    async def test_timeout_returns_error(self):
        with patch("api.services.wireguard._CMD_TIMEOUT", 0.1):
            out, err, rc = await _run(["sleep", "10"])
            assert rc == 1
            assert "timed out" in err
            assert out == ""


# ---------------------------------------------------------------------------
# _conf_path
# ---------------------------------------------------------------------------


class TestConfPath:
    def test_valid_name(self, tmp_path):
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            result = _conf_path("wg0")
            assert result == tmp_path / "wg0.conf"

    def test_path_traversal_rejected(self, tmp_path):
        with (
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(ValueError, match="Invalid interface name"),
        ):
            _conf_path("../etc/passwd")


# ---------------------------------------------------------------------------
# _read_conf_address
# ---------------------------------------------------------------------------


class TestReadConfAddress:
    def test_reads_address(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nAddress = 10.0.0.1/24\nListenPort = 51820\n")
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            assert _read_conf_address("wg0") == "10.0.0.1/24"

    def test_missing_conf(self, tmp_path):
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            assert _read_conf_address("wg0") is None

    def test_no_address_line(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nListenPort = 51820\n")
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            assert _read_conf_address("wg0") is None

    def test_case_insensitive(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\naddress = 10.0.0.1/24\n")
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            assert _read_conf_address("wg0") == "10.0.0.1/24"

    def test_multiple_address_lines(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nAddress = 10.0.0.1/24\nAddress = fd00::1/64\n")
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            assert _read_conf_address("wg0") == "10.0.0.1/24, fd00::1/64"


# ---------------------------------------------------------------------------
# _parse_peers_dump
# ---------------------------------------------------------------------------


class TestParsePeersDump:
    def test_parses_peer_line(self):
        line = f"{VALID_KEY}\t(none)\t1.2.3.4:51820\t10.0.0.2/32\t1700000000\t1024\t2048\toff"
        peers = _parse_peers_dump([line])
        assert len(peers) == 1
        assert peers[0]["public_key"] == VALID_KEY
        assert peers[0]["endpoint"] == "1.2.3.4:51820"
        assert peers[0]["preshared_key"] is None
        assert peers[0]["persistent_keepalive"] is None

    def test_parses_multiple_peers(self):
        lines = [
            f"{VALID_KEY}\t(none)\t1.2.3.4:51820\t10.0.0.2/32\t0\t0\t0\toff",
            f"{VALID_KEY}\t(none)\t5.6.7.8:51820\t10.0.0.3/32\t0\t0\t0\t25",
        ]
        peers = _parse_peers_dump(lines)
        assert len(peers) == 2
        assert peers[1]["persistent_keepalive"] == 25

    def test_skips_short_lines(self):
        peers = _parse_peers_dump(["too\tfew\tfields"])
        assert peers == []

    def test_empty_input(self):
        assert _parse_peers_dump([]) == []

    def test_none_values(self):
        line = f"{VALID_KEY}\t(none)\t(none)\t(none)\t0\t0\t0\toff"
        peers = _parse_peers_dump([line])
        assert peers[0]["endpoint"] is None
        assert peers[0]["allowed_ips"] is None
        assert peers[0]["latest_handshake"] is None


# ---------------------------------------------------------------------------
# list_interfaces (wg show all dump)
# ---------------------------------------------------------------------------


class TestListInterfaces:
    @pytest.fixture
    def mock_wg(self, tmp_path):
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            yield mock_run, tmp_path

    async def test_single_interface_no_peers(self, mock_wg):
        mock_run, tmp_path = mock_wg
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nAddress = 10.0.0.1/24\n")
        mock_run.return_value = (f"wg0\tPRIVATE\t{VALID_KEY}\t51820\toff", "", 0)

        result = await list_interfaces()
        assert len(result) == 1
        assert result[0]["name"] == "wg0"
        assert result[0]["public_key"] == VALID_KEY
        assert result[0]["num_peers"] == 0
        assert result[0]["address"] == "10.0.0.1/24"

    async def test_interface_with_peers(self, mock_wg):
        mock_run, tmp_path = mock_wg
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nAddress = 10.0.0.1/24\n")
        dump = (
            f"wg0\tPRIVATE\t{VALID_KEY}\t51820\toff\nwg0\t{VALID_KEY}\t(none)\t1.2.3.4:51820\t10.0.0.2/32\t0\t0\t0\toff"
        )
        mock_run.return_value = (dump, "", 0)

        result = await list_interfaces()
        assert result[0]["num_peers"] == 1

    async def test_empty_when_no_interfaces(self, mock_wg):
        mock_run, _ = mock_wg
        mock_run.return_value = ("", "", 0)
        assert await list_interfaces() == []

    async def test_empty_on_error(self, mock_wg):
        mock_run, _ = mock_wg
        mock_run.return_value = ("", "error", 1)
        assert await list_interfaces() == []


# ---------------------------------------------------------------------------
# get_interface
# ---------------------------------------------------------------------------


class TestGetInterface:
    async def test_returns_interface(self, tmp_path):
        dump = f"{VALID_KEY}\t{VALID_KEY}\t51820\toff"
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=(dump, "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            conf = tmp_path / "wg0.conf"
            conf.write_text("[Interface]\nAddress = 10.0.0.1/24\n")
            result = await get_interface("wg0")
            assert result is not None
            assert result["name"] == "wg0"
            assert result["address"] == "10.0.0.1/24"

    async def test_returns_none_on_error(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)):
            assert await get_interface("wg0") is None


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


