from unittest.mock import patch

import pytest

from api.services.wireguard import (
    _conf_path,
    _interface_from_dump,
    _parse_peers_dump,
    _run,
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
# _parse_peers_dump
# ---------------------------------------------------------------------------


class TestParsePeersDump:
    def test_parses_peer_line(self):
        line = f"{VALID_KEY}\t(none)\t1.2.3.4:51820\t10.0.0.2/32\t1700000000\t1024\t2048\toff"
        peers = _parse_peers_dump([line])
        assert len(peers) == 1
        assert peers[0].public_key == VALID_KEY
        assert peers[0].endpoint == "1.2.3.4:51820"
        assert peers[0].preshared_key is None
        assert peers[0].persistent_keepalive is None

    def test_parses_multiple_peers(self):
        lines = [
            f"{VALID_KEY}\t(none)\t1.2.3.4:51820\t10.0.0.2/32\t0\t0\t0\toff",
            f"{VALID_KEY}\t(none)\t5.6.7.8:51820\t10.0.0.3/32\t0\t0\t0\t25",
        ]
        peers = _parse_peers_dump(lines)
        assert len(peers) == 2
        assert peers[1].persistent_keepalive == 25

    def test_skips_short_lines(self):
        peers = _parse_peers_dump(["too\tfew\tfields"])
        assert peers == []

    def test_empty_input(self):
        assert _parse_peers_dump([]) == []

    def test_none_values(self):
        line = f"{VALID_KEY}\t(none)\t(none)\t(none)\t0\t0\t0\toff"
        peers = _parse_peers_dump([line])
        assert peers[0].endpoint is None
        assert peers[0].allowed_ips is None
        assert peers[0].latest_handshake is None

    def test_malformed_line_skipped(self):
        line = f"{VALID_KEY}\t(none)\t(none)\t(none)\tBAD\tBAD\tBAD\toff"
        peers = _parse_peers_dump([line])
        assert peers == []


# ---------------------------------------------------------------------------
# _interface_from_dump
# ---------------------------------------------------------------------------


class TestInterfaceFromDump:
    def test_parses_fields(self):
        iface = _interface_from_dump("wg0", ["PRIVATE", VALID_KEY, "51820", "0x1234"])
        assert iface.name == "wg0"
        assert iface.status == "up"
        assert iface.public_key == VALID_KEY
        assert iface.listen_port == 51820
        assert iface.fw_mark == "0x1234"

    def test_none_values(self):
        iface = _interface_from_dump("wg0", ["(none)", "(none)", "0", "off"])
        assert iface.public_key is None
        assert iface.listen_port is None
        assert iface.fw_mark is None

    async def test_undecodable_output_is_replaced(self):
        out, err, rc = await _run(["printf", "\\377ok"])
        assert rc == 0
        assert out == "�ok"
