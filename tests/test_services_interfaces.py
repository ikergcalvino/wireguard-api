import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from api.models.interfaces import Interface
from api.services.wireguard import (
    create_interface,
    delete_interface,
    get_interface,
    interface_down,
    interface_save,
    interface_up,
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
        assert result[0].name == "wg0"
        assert result[0].public_key == VALID_KEY
        assert result[0].num_peers == 0
        assert result[0].address == "10.0.0.1/24"
        assert result[0].status == "up"

    async def test_interface_with_peers(self, mock_wg):
        mock_run, tmp_path = mock_wg
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nAddress = 10.0.0.1/24\n")
        dump = (
            f"wg0\tPRIVATE\t{VALID_KEY}\t51820\toff\nwg0\t{VALID_KEY}\t(none)\t1.2.3.4:51820\t10.0.0.2/32\t0\t0\t0\toff"
        )
        mock_run.return_value = (dump, "", 0)

        result = await list_interfaces()
        assert result[0].num_peers == 1
        assert result[0].status == "up"

    async def test_shows_down_interfaces(self, mock_wg):
        mock_run, tmp_path = mock_wg
        mock_run.return_value = ("", "", 0)
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nAddress = 10.0.0.1/24\nListenPort = 51820\n")

        result = await list_interfaces()
        assert len(result) == 1
        assert result[0].name == "wg0"
        assert result[0].status == "down"
        assert result[0].address == "10.0.0.1/24"

    async def test_shows_both_up_and_down(self, mock_wg):
        mock_run, tmp_path = mock_wg
        mock_run.return_value = (f"wg0\tPRIVATE\t{VALID_KEY}\t51820\toff", "", 0)
        (tmp_path / "wg0.conf").write_text("[Interface]\nAddress = 10.0.0.1/24\n")
        (tmp_path / "wg1.conf").write_text("[Interface]\nAddress = 10.0.1.1/24\n")

        result = await list_interfaces()
        assert len(result) == 2
        names = {r.name: r.status for r in result}
        assert names["wg0"] == "up"
        assert names["wg1"] == "down"

    async def test_empty_when_no_interfaces(self, mock_wg):
        mock_run, _ = mock_wg
        mock_run.return_value = ("", "", 0)
        assert await list_interfaces() == []

    async def test_empty_on_error(self, mock_wg):
        mock_run, _ = mock_wg
        mock_run.return_value = ("", "error", 1)
        assert await list_interfaces() == []

    async def test_skips_invalid_conf_names(self, mock_wg):
        mock_run, tmp_path = mock_wg
        mock_run.return_value = ("", "", 0)
        (tmp_path / "wg0.conf").write_text("[Interface]\nAddress = 10.0.0.1/24\n")
        (tmp_path / "inv@lid.conf").write_text("[Interface]\nAddress = 10.0.0.2/24\n")
        result = await list_interfaces()
        assert len(result) == 1
        assert result[0].name == "wg0"


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
            assert result.name == "wg0"
            assert result.address == "10.0.0.1/24"
            assert result.status == "up"

    async def test_returns_none_when_no_conf(self, tmp_path):
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            assert await get_interface("wg0") is None

    async def test_returns_down_interface_from_conf(self, tmp_path):
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            conf = tmp_path / "wg0.conf"
            conf.write_text(
                f"[Interface]\nAddress = 10.0.0.1/24\n\n[Peer]\nPublicKey = {VALID_KEY}\nAllowedIPs = 10.0.0.2/32\n"
            )
            result = await get_interface("wg0")
            assert result is not None
            assert result.name == "wg0"
            assert result.status == "down"
            assert result.num_peers == 1


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
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            mock_run.side_effect = [
                ("PRIVATE\tPUBLIC\t51820\toff", "", 0),  # wg show dump (list_peers)
                ("PRIVATE\tPUBLIC\t51820\toff", "", 0),  # wg show dump (check if up)
                ("", "", 0),  # wg syncconf
            ]
            stderr, rc = await update_interface("wg0", iface)
            assert rc == 0
            content = (tmp_path / "wg0.conf").read_text()
            assert "10.0.0.2/24" in content
            assert not (tmp_path / "wg0.conf.bak").exists()

    async def test_preserves_peers(self, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\nAddress = 10.0.0.1/24\n")
        iface = Interface(name="wg0", address="10.0.0.2/24", private_key=VALID_KEY)
        peer_dump = f"PRIVATE\tPUBLIC\t51820\toff\n{VALID_KEY}\t(none)\t1.2.3.4:51820\t10.0.0.2/32\t0\t0\t0\toff"
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            mock_run.side_effect = [
                (peer_dump, "", 0),  # wg show dump (list_peers)
                (peer_dump, "", 0),  # wg show dump (check if up)
                ("", "", 0),  # wg syncconf
            ]
            stderr, rc = await update_interface("wg0", iface)
            assert rc == 0
            content = (tmp_path / "wg0.conf").read_text()
            assert "[Peer]" in content
            assert VALID_KEY in content
            assert "10.0.0.2/32" in content

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

    async def test_missing_address(self, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\n")
        iface = Interface(name="wg0", private_key=VALID_KEY)
        with (
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(ValueError, match="address"),
        ):
            await update_interface("wg0", iface)

    async def test_down_interface_preserves_conf_peers(self, tmp_path):
        (tmp_path / "wg0.conf").write_text(
            f"[Interface]\nAddress = 10.0.0.1/24\nPrivateKey = old\n\n"
            f"[Peer]\nPublicKey = {VALID_KEY}\nAllowedIPs = 10.0.0.2/32\n"
        )
        iface = Interface(name="wg0", address="10.0.0.1/24", private_key=VALID_KEY, listen_port=51821)
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            mock_run.side_effect = [
                ("", "err", 1),  # wg show dump (list_peers fails → reads .conf)
                ("", "err", 1),  # wg show dump (check if up → skip syncconf)
            ]
            stderr, rc = await update_interface("wg0", iface)
            assert rc == 0
            content = (tmp_path / "wg0.conf").read_text()
            assert "[Peer]" in content
            assert VALID_KEY in content
            assert "ListenPort = 51821" in content

    async def test_syncconf_failure_restores_backup(self, tmp_path):
        original = "[Interface]\nAddress = 10.0.0.1/24\nPrivateKey = old\n"
        (tmp_path / "wg0.conf").write_text(original)
        iface = Interface(name="wg0", address="10.0.0.2/24", private_key=VALID_KEY)
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            mock_run.side_effect = [
                ("PRIVATE\tPUBLIC\t51820\toff", "", 0),  # wg show dump (list_peers)
                ("PRIVATE\tPUBLIC\t51820\toff", "", 0),  # wg show dump (check if up)
                ("", "syncconf failed", 1),  # wg syncconf fails
            ]
            stderr, rc = await update_interface("wg0", iface)
            assert rc == 1
            content = (tmp_path / "wg0.conf").read_text()
            assert content == original


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

    async def test_deletes_down_interface(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\nAddress = 10.0.0.1/24\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            mock_run.side_effect = [
                ("", "not running", 1),  # wg-quick down fails
                ("", "err", 1),  # wg show dump — not running
            ]
            stderr, rc = await delete_interface("wg0")
            assert rc == 0
            assert not conf.exists()

    async def test_returns_error_if_up_but_down_fails(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            mock_run.side_effect = [
                ("", "some error", 1),  # wg-quick down fails
                ("PRIVATE\tPUBLIC\t51820\toff", "", 0),  # wg show dump — still running
            ]
            stderr, rc = await delete_interface("wg0")
            assert rc == 1
            assert conf.exists()

    async def test_cleans_up_bak_file(self, tmp_path):
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\n")
        bak = tmp_path / "wg0.conf.bak"
        bak.write_text("[Interface]\nold backup\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            stderr, rc = await delete_interface("wg0")
            assert rc == 0
            assert not conf.exists()
            assert not bak.exists()

    async def test_not_found(self, tmp_path):
        with (
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(FileNotFoundError),
        ):
            await delete_interface("wg0")

    async def test_cleans_up_update_lock(self, tmp_path):
        from api.services.wireguard import _update_locks

        _update_locks["wg0"] = asyncio.Lock()
        conf = tmp_path / "wg0.conf"
        conf.write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            await delete_interface("wg0")
            assert "wg0" not in _update_locks


# ---------------------------------------------------------------------------
# interface_up / interface_down / interface_save
# ---------------------------------------------------------------------------


class TestInterfaceUp:
    async def test_success(self, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            stderr, rc = await interface_up("wg0")
            assert rc == 0

    async def test_not_found(self, tmp_path):
        with (
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(FileNotFoundError),
        ):
            await interface_up("wg0")


class TestInterfaceDown:
    async def test_success(self, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            stderr, rc = await interface_down("wg0")
            assert rc == 0

    async def test_not_found(self, tmp_path):
        with (
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(FileNotFoundError),
        ):
            await interface_down("wg0")


class TestInterfaceSave:
    async def test_success(self, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            stderr, rc = await interface_save("wg0")
            assert rc == 0

    async def test_not_found(self, tmp_path):
        with (
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(FileNotFoundError),
        ):
            await interface_save("wg0")
