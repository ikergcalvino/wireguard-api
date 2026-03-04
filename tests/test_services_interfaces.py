from unittest.mock import AsyncMock, patch

import pytest

from api.models.interfaces import Interface
from api.services.wireguard import (
    create_interface,
    delete_interface,
    get_interface,
    list_interfaces,
    update_interface,
)
from tests.conftest import VALID_KEY

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
# create_interface
# ---------------------------------------------------------------------------


class TestCreateInterface:
    async def test_success(self, tmp_path):
        iface = Interface(name="wg0", address="10.0.0.1/24", private_key=VALID_KEY)
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            stderr, rc = await create_interface(iface)
            assert rc == 0
            conf = tmp_path / "wg0.conf"
            assert conf.exists()
            content = conf.read_text()
            assert "10.0.0.1/24" in content
            assert VALID_KEY in content

    async def test_missing_private_key(self, tmp_path):
        iface = Interface(name="wg0", address="10.0.0.1/24")
        with (
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(ValueError, match="private_key"),
        ):
            await create_interface(iface)

    async def test_missing_address(self, tmp_path):
        iface = Interface(name="wg0", private_key=VALID_KEY)
        with (
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(ValueError, match="address"),
        ):
            await create_interface(iface)

    async def test_duplicate(self, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\n")
        iface = Interface(name="wg0", address="10.0.0.1/24", private_key=VALID_KEY)
        with (
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(FileExistsError),
        ):
            await create_interface(iface)

    async def test_cleans_up_on_failure(self, tmp_path):
        iface = Interface(name="wg0", address="10.0.0.1/24", private_key=VALID_KEY)
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "fail", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            stderr, rc = await create_interface(iface)
            assert rc == 1
            assert not (tmp_path / "wg0.conf").exists()

    async def test_conf_permissions(self, tmp_path):
        iface = Interface(name="wg0", address="10.0.0.1/24", private_key=VALID_KEY)
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            await create_interface(iface)
            conf = tmp_path / "wg0.conf"
            assert oct(conf.stat().st_mode & 0o777) == "0o600"


# ---------------------------------------------------------------------------
# update_interface
# ---------------------------------------------------------------------------


class TestUpdateInterface:
    async def test_success(self, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\nAddress = 10.0.0.1/24\n")
        iface = Interface(name="wg0", address="10.0.0.2/24", private_key=VALID_KEY)
        with patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path):
            stderr, rc = await update_interface("wg0", iface)
            assert rc == 0
            content = (tmp_path / "wg0.conf").read_text()
            assert "10.0.0.2/24" in content

    async def test_not_found(self, tmp_path):
        iface = Interface(name="wg0", address="10.0.0.1/24", private_key=VALID_KEY)
        with (
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(FileNotFoundError),
        ):
            await update_interface("wg0", iface)

    async def test_missing_private_key(self, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\n")
        iface = Interface(name="wg0", address="10.0.0.1/24")
        with (
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(ValueError, match="private_key"),
        ):
            await update_interface("wg0", iface)


# ---------------------------------------------------------------------------
# delete_interface
# ---------------------------------------------------------------------------


class TestDeleteInterface:
    async def test_success(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            stderr, rc = await delete_interface("wg0")
            assert rc == 0
            assert not conf.exists()

    async def test_deletes_conf_even_if_down_fails(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "not running", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            stderr, rc = await delete_interface("wg0")
            assert rc == 0
            assert not conf.exists()

    async def test_not_found(self, tmp_path):
        with (
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(FileNotFoundError),
        ):
            await delete_interface("wg0")
