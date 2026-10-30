import pytest
from pydantic import ValidationError

from api.models.interfaces import Interface, InterfaceUpdate
from api.models.peers import Peer
from tests.conftest import VALID_KEY

INVALID_KEY = "not-a-valid-key"


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class TestInterface:
    def test_runtime_fields(self):
        iface = Interface(
            name="wg0",
            status="up",
            public_key=VALID_KEY,
            listen_port=51820,
            fw_mark="0x1234",
            num_peers=3,
        )
        assert iface.num_peers == 3
        assert iface.fw_mark == "0x1234"

    def test_minimal(self):
        iface = Interface(name="wg0", status="down")
        assert iface.num_peers == 0
        assert iface.public_key is None
        assert iface.listen_port is None

    def test_invalid_name_too_long(self):
        with pytest.raises(ValidationError, match="1-15"):
            Interface(name="a" * 16, status="down")

    def test_invalid_name_special_chars(self):
        with pytest.raises(ValidationError, match="1-15"):
            Interface(name="wg@0", status="down")

    def test_valid_name_with_dots_and_equals(self):
        iface = Interface(name="wg.vpn=0", status="down")
        assert iface.name == "wg.vpn=0"

    def test_invalid_public_key(self):
        with pytest.raises(ValidationError, match="key format"):
            Interface(name="wg0", status="up", public_key=INVALID_KEY)

    def test_has_no_private_key(self):
        assert "private_key" not in Interface.model_fields


class TestInterfaceUpdate:
    def test_valid_full(self):
        update = InterfaceUpdate(private_key=VALID_KEY, listen_port=51820, fw_mark="off")
        assert update.listen_port == 51820

    def test_empty(self):
        assert InterfaceUpdate().model_dump(exclude_unset=True) == {}

    def test_invalid_private_key(self):
        with pytest.raises(ValidationError, match="key format"):
            InterfaceUpdate(private_key=INVALID_KEY)

    @pytest.mark.parametrize("port", [0, 70000])
    def test_invalid_listen_port(self, port):
        with pytest.raises(ValidationError):
            InterfaceUpdate(listen_port=port)

    @pytest.mark.parametrize("mark", ["off", "0", "1234", "0x1234", "0xFFFFFFFF"])
    def test_valid_fw_mark(self, mark):
        assert InterfaceUpdate(fw_mark=mark).fw_mark == mark

    @pytest.mark.parametrize("mark", ["", "on", "0x", "-1", "0x123456789", "1\nPostUp = id"])
    def test_invalid_fw_mark(self, mark):
        with pytest.raises(ValidationError, match="fw_mark"):
            InterfaceUpdate(fw_mark=mark)

    @pytest.mark.parametrize("field", ["name", "address", "dns", "post_up", "save_config"])
    def test_wg_quick_and_unknown_fields_forbidden(self, field):
        with pytest.raises(ValidationError, match="extra"):
            InterfaceUpdate(**{field: "x"})


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

    def test_valid_allowed_ips(self):
        peer = Peer(public_key=VALID_KEY, allowed_ips="10.0.0.2/32")
        assert peer.allowed_ips == "10.0.0.2/32"

    def test_comma_separated_allowed_ips(self):
        peer = Peer(public_key=VALID_KEY, allowed_ips="10.0.0.0/24, fd00::/64")
        assert peer.allowed_ips == "10.0.0.0/24, fd00::/64"

    def test_catch_all_allowed_ips(self):
        peer = Peer(public_key=VALID_KEY, allowed_ips="0.0.0.0/0, ::/0")
        assert peer.allowed_ips == "0.0.0.0/0, ::/0"

    def test_invalid_allowed_ips(self):
        with pytest.raises(ValidationError, match="CIDR"):
            Peer(public_key=VALID_KEY, allowed_ips="not-a-cidr")

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


class TestPeerEndpoint:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "1.2.3.4:51820",
            "[fd00::1]:51820",
            "[fe80::1%eth0]:51820",
            "vpn.example.com:51820",
            "localhost:1",
            "host-1:65535",
        ],
    )
    def test_valid(self, endpoint):
        assert Peer(public_key=VALID_KEY, endpoint=endpoint).endpoint == endpoint

    @pytest.mark.parametrize(
        "endpoint",
        [
            "",
            "1.2.3.4",
            "1.2.3.4:",
            "1.2.3.4:0",
            "1.2.3.4:65536",
            "1.2.3.4:51820x",
            "fd00::1:51820",
            "[not-an-ip]:51820",
            "[1.2.3.4]:51820",
            "-bad.example.com:51820",
            "bad_host:51820",
            "host:51820\nPostUp = id",
            "1.2.3.4:51820 extra",
        ],
    )
    def test_invalid(self, endpoint):
        with pytest.raises(ValidationError, match="Invalid endpoint"):
            Peer(public_key=VALID_KEY, endpoint=endpoint)
