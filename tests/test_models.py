import pytest
from pydantic import ValidationError

from api.models.interfaces import Interface
from api.models.peers import Peer
from tests.conftest import VALID_KEY

INVALID_KEY = "not-a-valid-key"


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class TestInterface:
    def test_valid_full(self):
        iface = Interface(
            name="wg0",
            address="10.0.0.1/24",
            listen_port=51820,
            private_key=VALID_KEY,
        )
        assert iface.name == "wg0"
        assert iface.address == "10.0.0.1/24"
        assert iface.listen_port == 51820

    def test_minimal(self):
        iface = Interface(name="wg0")
        assert iface.num_peers == 0
        assert iface.public_key is None
        assert iface.listen_port is None

    def test_invalid_name_too_long(self):
        with pytest.raises(ValidationError, match="1-15"):
            Interface(name="a" * 16)

    def test_invalid_name_special_chars(self):
        with pytest.raises(ValidationError, match="1-15"):
            Interface(name="wg@0")

    def test_valid_name_with_dots_and_equals(self):
        iface = Interface(name="wg.vpn=0")
        assert iface.name == "wg.vpn=0"

    def test_invalid_address(self):
        with pytest.raises(ValidationError, match="CIDR"):
            Interface(name="wg0", address="not-an-ip")

    def test_comma_separated_addresses(self):
        iface = Interface(name="wg0", address="10.0.0.1/24, fd00::1/64")
        assert iface.address == "10.0.0.1/24, fd00::1/64"

    def test_invalid_private_key(self):
        with pytest.raises(ValidationError, match="key format"):
            Interface(name="wg0", private_key=INVALID_KEY)

    def test_invalid_public_key(self):
        with pytest.raises(ValidationError, match="key format"):
            Interface(name="wg0", public_key=INVALID_KEY)

    def test_invalid_listen_port_too_high(self):
        with pytest.raises(ValidationError):
            Interface(name="wg0", listen_port=70000)

    def test_invalid_listen_port_zero(self):
        with pytest.raises(ValidationError):
            Interface(name="wg0", listen_port=0)

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError, match="extra"):
            Interface(name="wg0", unknown_field="x")

    def test_ipv6_address(self):
        iface = Interface(name="wg0", address="fd00::1/64")
        assert iface.address == "fd00::1/64"

    def test_all_wg_quick_fields(self):
        iface = Interface(
            name="wg0",
            address="10.0.0.1/24",
            private_key=VALID_KEY,
            listen_port=51820,
            dns="1.1.1.1, 8.8.8.8",
            mtu=1420,
            table="auto",
            pre_up="echo pre-up",
            post_up="iptables -A FORWARD -i wg0 -j ACCEPT",
            pre_down="echo pre-down",
            post_down="iptables -D FORWARD -i wg0 -j ACCEPT",
            save_config=True,
        )
        assert iface.dns == "1.1.1.1, 8.8.8.8"
        assert iface.mtu == 1420
        assert iface.save_config is True

    def test_runtime_fields(self):
        iface = Interface(
            name="wg0",
            public_key=VALID_KEY,
            listen_port=51820,
            address="10.0.0.1/24",
            fw_mark="0x1234",
            num_peers=3,
        )
        assert iface.num_peers == 3
        assert iface.fw_mark == "0x1234"


# ---------------------------------------------------------------------------
# Peer
# ---------------------------------------------------------------------------


class TestPeer:
    def test_valid(self):
        peer = Peer(public_key=VALID_KEY, allowed_ips="10.0.0.2/32")
        assert peer.public_key == VALID_KEY

    def test_minimal(self):
        peer = Peer()
        assert peer.public_key is None
        assert peer.allowed_ips is None

    def test_invalid_public_key(self):
        with pytest.raises(ValidationError, match="key format"):
            Peer(public_key=INVALID_KEY)

    def test_invalid_preshared_key(self):
        with pytest.raises(ValidationError, match="key format"):
            Peer(public_key=VALID_KEY, preshared_key=INVALID_KEY)

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError, match="extra"):
            Peer(public_key=VALID_KEY, unknown="x")

    def test_persistent_keepalive_range(self):
        with pytest.raises(ValidationError):
            Peer(public_key=VALID_KEY, persistent_keepalive=-1)
        with pytest.raises(ValidationError):
            Peer(public_key=VALID_KEY, persistent_keepalive=70000)

    def test_all_wg_fields(self):
        peer = Peer(
            public_key=VALID_KEY,
            allowed_ips="10.0.0.2/32",
            endpoint="1.2.3.4:51820",
            preshared_key=VALID_KEY,
            persistent_keepalive=25,
        )
        assert peer.endpoint == "1.2.3.4:51820"
        assert peer.persistent_keepalive == 25

    def test_runtime_fields(self):
        peer = Peer(
            public_key=VALID_KEY,
            allowed_ips="10.0.0.2/32",
            endpoint="1.2.3.4:51820",
            latest_handshake=1700000000,
            transfer_rx=1024,
            transfer_tx=2048,
            persistent_keepalive=25,
        )
        assert peer.transfer_rx == 1024
