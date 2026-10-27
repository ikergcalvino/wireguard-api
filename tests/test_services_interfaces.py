from unittest.mock import AsyncMock, call, patch

import pytest

from api.models.interfaces import InterfaceUpdate
from api.services.wireguard import (
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
        mock_run, _ = mock_wg
        mock_run.return_value = (f"wg0\tPRIVATE\t{VALID_KEY}\t51820\toff", "", 0)

        result = await list_interfaces()
        assert len(result) == 1
        assert result[0].name == "wg0"
        assert result[0].public_key == VALID_KEY
        assert result[0].listen_port == 51820
        assert result[0].num_peers == 0
        assert result[0].status == "up"

    async def test_interface_with_peers(self, mock_wg):
        mock_run, _ = mock_wg
        dump = (
            f"wg0\tPRIVATE\t{VALID_KEY}\t51820\toff\nwg0\t{VALID_KEY}\t(none)\t1.2.3.4:51820\t10.0.0.2/32\t0\t0\t0\toff"
        )
        mock_run.return_value = (dump, "", 0)

        result = await list_interfaces()
        assert result[0].num_peers == 1
        assert result[0].status == "up"

    async def test_running_interface_without_conf_is_listed(self, mock_wg):
        mock_run, tmp_path = mock_wg
        mock_run.return_value = (f"wg0\tPRIVATE\t{VALID_KEY}\t51820\toff", "", 0)

        result = await list_interfaces()
        assert [i.name for i in result] == ["wg0"]

    async def test_down_interfaces_listed_by_name_only(self, mock_wg):
        mock_run, tmp_path = mock_wg
        mock_run.return_value = ("", "", 0)
        (tmp_path / "wg0.conf").write_text("[Interface]\nListenPort = 51820\n")

        result = await list_interfaces()
        assert len(result) == 1
        assert result[0].name == "wg0"
        assert result[0].status == "down"
        assert result[0].listen_port is None

    async def test_conf_contents_are_not_read(self, mock_wg):
        mock_run, tmp_path = mock_wg
        mock_run.return_value = ("", "", 0)
        (tmp_path / "wg0.conf").write_text("garbage that is not a WireGuard config")

        result = await list_interfaces()
        assert result[0].name == "wg0"

    async def test_shows_both_up_and_down(self, mock_wg):
        mock_run, tmp_path = mock_wg
        mock_run.return_value = (f"wg0\tPRIVATE\t{VALID_KEY}\t51820\toff", "", 0)
        (tmp_path / "wg0.conf").write_text("")
        (tmp_path / "wg1.conf").write_text("")

        result = await list_interfaces()
        assert {r.name: r.status for r in result} == {"wg0": "up", "wg1": "down"}

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
        (tmp_path / "wg0.conf").write_text("")
        (tmp_path / "inv@lid.conf").write_text("")
        result = await list_interfaces()
        assert [i.name for i in result] == ["wg0"]


# ---------------------------------------------------------------------------
# get_interface
# ---------------------------------------------------------------------------


class TestGetInterface:
    async def test_returns_running_interface(self, tmp_path):
        dump = f"PRIVATE\t{VALID_KEY}\t51820\toff\n{VALID_KEY}\t(none)\t(none)\t10.0.0.2/32\t0\t0\t0\toff"
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=(dump, "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            result = await get_interface("wg0")
            assert result is not None
            assert result.name == "wg0"
            assert result.public_key == VALID_KEY
            assert result.listen_port == 51820
            assert result.num_peers == 1
            assert result.status == "up"

    async def test_returns_down_interface_when_conf_exists(self, tmp_path):
        (tmp_path / "wg0.conf").write_text("[Interface]\nListenPort = 1111\n")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            result = await get_interface("wg0")
            assert result is not None
            assert result.status == "down"
            assert result.listen_port is None

    async def test_returns_none_when_not_running_and_no_conf(self, tmp_path):
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "err", 1)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            assert await get_interface("wg0") is None


# ---------------------------------------------------------------------------
# update_interface (wg set)
# ---------------------------------------------------------------------------


class TestUpdateInterface:
    async def test_sets_all_fields(self):
        update = InterfaceUpdate(private_key=VALID_KEY, listen_port=51821, fw_mark="0x10")
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)) as mock_run:
            assert await update_interface("wg0", update) == ("", 0)
        assert mock_run.await_args_list == [
            call(
                ["wg", "set", "wg0", "private-key", "/dev/stdin", "listen-port", "51821", "fwmark", "0x10"],
                stdin_data=VALID_KEY.encode(),
            )
        ]

    async def test_omitted_fields_are_left_unchanged(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)) as mock_run:
            await update_interface("wg0", InterfaceUpdate(listen_port=51821))
        assert mock_run.await_args_list == [call(["wg", "set", "wg0", "listen-port", "51821"], stdin_data=None)]

    async def test_does_not_write_files(self, tmp_path):
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)),
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            await update_interface("wg0", InterfaceUpdate(private_key=VALID_KEY))
        assert list(tmp_path.iterdir()) == []

    async def test_returns_wg_error(self):
        with patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "No such device", 1)):
            assert await update_interface("wg0", InterfaceUpdate(listen_port=51821)) == ("No such device", 1)


# ---------------------------------------------------------------------------
# Lifecycle (wg-quick)
# ---------------------------------------------------------------------------


class TestLifecycle:
    @pytest.mark.parametrize(
        ("func", "action"),
        [(interface_up, "up"), (interface_down, "down"), (interface_save, "save")],
    )
    async def test_runs_wg_quick(self, tmp_path, func, action):
        (tmp_path / "wg0.conf").write_text("")
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock, return_value=("", "", 0)) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
        ):
            assert await func("wg0") == ("", 0)
        mock_run.assert_awaited_once_with(["wg-quick", action, "wg0"])

    @pytest.mark.parametrize("func", [interface_up, interface_down, interface_save])
    async def test_requires_conf(self, tmp_path, func):
        with (
            patch("api.services.wireguard._run", new_callable=AsyncMock) as mock_run,
            patch("api.services.wireguard.WG_CONFIG_DIR", tmp_path),
            pytest.raises(FileNotFoundError),
        ):
            await func("wg0")
        mock_run.assert_not_awaited()
