from unittest.mock import patch

import pytest

from api.models.interfaces import Interface
from api.models.peers import Peer
from api.services.wireguard import (
    _build_conf_content,
    _conf_path,
    _parse_conf_file,
    _parse_peers_dump,
    _read_conf_address,
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

    def test_stops_at_peer_section(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nAddress = 10.0.0.1/24\n\n[Peer]\nAllowedIPs = 10.0.0.2/32\n")
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            assert _read_conf_address("wg0") == "10.0.0.1/24"


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
# _build_conf_content
# ---------------------------------------------------------------------------


class TestBuildConfContent:
    def test_minimal(self):
        iface = Interface(name="wg0", address="10.0.0.1/24", private_key=VALID_KEY)
        content = _build_conf_content(iface).decode()
        assert "[Interface]" in content
        assert "Address = 10.0.0.1/24" in content
        assert f"PrivateKey = {VALID_KEY}" in content

    def test_all_interface_fields(self):
        iface = Interface(
            name="wg0",
            address="10.0.0.1/24",
            private_key=VALID_KEY,
            listen_port=51820,
            dns="1.1.1.1",
            mtu=1420,
            table="auto",
            pre_up="echo pre",
            post_up="echo post",
            pre_down="echo predown",
            post_down="echo postdown",
            save_config=True,
        )
        content = _build_conf_content(iface).decode()
        assert "ListenPort = 51820" in content
        assert "DNS = 1.1.1.1" in content
        assert "MTU = 1420" in content
        assert "Table = auto" in content
        assert "PreUp = echo pre" in content
        assert "PostUp = echo post" in content
        assert "PreDown = echo predown" in content
        assert "PostDown = echo postdown" in content
        assert "SaveConfig = true" in content

    def test_with_peers(self):
        iface = Interface(name="wg0", address="10.0.0.1/24", private_key=VALID_KEY)
        peers = [
            Peer(public_key=VALID_KEY, allowed_ips="10.0.0.2/32", endpoint="1.2.3.4:51820"),
        ]
        content = _build_conf_content(iface, peers=peers).decode()
        assert "[Peer]" in content
        assert f"PublicKey = {VALID_KEY}" in content
        assert "AllowedIPs = 10.0.0.2/32" in content
        assert "Endpoint = 1.2.3.4:51820" in content

    def test_peer_with_keepalive(self):
        iface = Interface(name="wg0", address="10.0.0.1/24", private_key=VALID_KEY)
        peers = [Peer(public_key=VALID_KEY, allowed_ips="10.0.0.2/32", persistent_keepalive=25)]
        content = _build_conf_content(iface, peers=peers).decode()
        assert "PersistentKeepalive = 25" in content

    def test_no_peers(self):
        iface = Interface(name="wg0", address="10.0.0.1/24", private_key=VALID_KEY)
        content = _build_conf_content(iface).decode()
        assert "[Peer]" not in content

    def test_empty_peers_list(self):
        iface = Interface(name="wg0", address="10.0.0.1/24", private_key=VALID_KEY)
        content = _build_conf_content(iface, peers=[]).decode()
        assert "[Peer]" not in content

    def test_ends_with_newline(self):
        iface = Interface(name="wg0", address="10.0.0.1/24", private_key=VALID_KEY)
        content = _build_conf_content(iface).decode()
        assert content.endswith("\n")


# ---------------------------------------------------------------------------
# _parse_conf_file
# ---------------------------------------------------------------------------


class TestParseConfFile:
    def test_returns_none_when_missing(self, tmp_path):
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            assert _parse_conf_file("wg0") is None

    def test_parses_interface(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nAddress = 10.0.0.1/24\nListenPort = 51820\n")
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            result = _parse_conf_file("wg0")
            assert result is not None
            iface, peers = result
            assert iface.name == "wg0"
            assert iface.address == "10.0.0.1/24"
            assert iface.listen_port == 51820
            assert iface.status == "down"
            assert peers == []

    def test_parses_peers(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text(
            "[Interface]\nAddress = 10.0.0.1/24\n\n"
            f"[Peer]\nPublicKey = {VALID_KEY}\nAllowedIPs = 10.0.0.2/32\n"
            f"Endpoint = 1.2.3.4:51820\nPersistentKeepalive = 25\n"
        )
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            result = _parse_conf_file("wg0")
            assert result is not None
            iface, peers = result
            assert iface.num_peers == 1
            assert len(peers) == 1
            assert peers[0].public_key == VALID_KEY
            assert peers[0].allowed_ips == "10.0.0.2/32"
            assert peers[0].endpoint == "1.2.3.4:51820"
            assert peers[0].persistent_keepalive == 25

    def test_parses_multiple_peers(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text(
            "[Interface]\nAddress = 10.0.0.1/24\n\n"
            f"[Peer]\nPublicKey = {VALID_KEY}\nAllowedIPs = 10.0.0.2/32\n\n"
            f"[Peer]\nPublicKey = {VALID_KEY}\nAllowedIPs = 10.0.0.3/32\n"
        )
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            result = _parse_conf_file("wg0")
            assert result is not None
            iface, peers = result
            assert iface.num_peers == 2
            assert len(peers) == 2

    def test_skips_comments_and_blank_lines(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("# Comment\n\n[Interface]\nAddress = 10.0.0.1/24\n")
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            result = _parse_conf_file("wg0")
            assert result is not None
            assert result[0].address == "10.0.0.1/24"

    def test_parses_all_interface_fields(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text(
            "[Interface]\nAddress = 10.0.0.1/24\nListenPort = 51820\n"
            "DNS = 1.1.1.1\nMTU = 1420\nTable = auto\n"
            "PreUp = echo pre\nPostUp = echo post\n"
            "PreDown = echo predown\nPostDown = echo postdown\n"
            "SaveConfig = true\n"
        )
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            result = _parse_conf_file("wg0")
            assert result is not None
            iface = result[0]
            assert iface.dns == "1.1.1.1"
            assert iface.mtu == 1420
            assert iface.table == "auto"
            assert iface.pre_up == "echo pre"
            assert iface.post_up == "echo post"
            assert iface.pre_down == "echo predown"
            assert iface.post_down == "echo postdown"
            assert iface.save_config is True
