from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from api.config import settings
from api.models import IFACE_NAME_PATTERN
from api.models.interfaces import Interface, InterfaceUpdate
from api.models.peers import Peer

logger = logging.getLogger("wireguard-api")

WG_CONFIG_DIR = settings.config_dir
_CMD_TIMEOUT = 30


class InterfaceNotFound(Exception):
    """The interface has no config file, so wg-quick cannot manage it."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Interface '{name}' not found")


class WireGuardError(Exception):
    """A wg or wg-quick command failed. The message is its error output."""


class WireGuardUnavailable(Exception):
    """A wg or wg-quick command could not be executed at all."""


async def _run(args: list[str], stdin_data: bytes | None = None) -> tuple[str, str, int]:
    logger.debug("exec: %s", args)
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if stdin_data else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        logger.error("cannot execute %s: %s", args[0], exc)
        raise WireGuardUnavailable(f"Cannot execute {args[0]}: {exc.strerror}") from exc
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=stdin_data),
            timeout=_CMD_TIMEOUT,
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        logger.error("cmd %s timed out after %ds", args, _CMD_TIMEOUT)
        return "", f"Command timed out after {_CMD_TIMEOUT}s", 1
    out = stdout.decode(errors="replace").strip()
    err = stderr.decode(errors="replace").strip()
    rc = proc.returncode or 0
    if rc != 0:
        logger.warning("cmd %s failed (rc=%d): %s", args, rc, err)
    return out, err, rc


async def _check(args: list[str], stdin_data: bytes | None = None) -> str:
    """Run a command and return its output, raising WireGuardError if it fails."""
    out, err, rc = await _run(args, stdin_data=stdin_data)
    if rc != 0:
        raise WireGuardError(err or f"{args[0]} exited with status {rc}")
    return out


def _conf_path(name: str) -> Path:
    conf = (WG_CONFIG_DIR / f"{name}.conf").resolve()
    if conf.parent != WG_CONFIG_DIR.resolve():
        raise ValueError(f"Invalid interface name: {name}")
    return conf


def _require_conf(name: str) -> Path:
    conf = _conf_path(name)
    if not conf.exists():
        raise InterfaceNotFound(name)
    return conf


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------


def _interface_from_dump(name: str, fields: list[str]) -> Interface:
    # fields: private-key, public-key, listen-port, fwmark
    _, public_key, listen_port, fw_mark = fields[:4]
    return Interface(
        name=name,
        status="up",
        public_key=public_key if public_key != "(none)" else None,
        listen_port=(int(listen_port) or None) if listen_port.isdigit() else None,
        fw_mark=fw_mark if fw_mark != "off" else None,
    )


async def list_interfaces() -> list[Interface]:
    interfaces: dict[str, Interface] = {}

    # Unlike `wg show <name>`, this only fails when wg itself cannot run
    # (e.g. missing CAP_NET_ADMIN): report it instead of listing everything as down.
    stdout = await _check(["wg", "show", "all", "dump"])
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 5:
            interfaces[parts[0]] = _interface_from_dump(parts[0], parts[1:])
        elif len(parts) == 9 and parts[0] in interfaces:
            interfaces[parts[0]].num_peers += 1

    # Config files are only used to know which interfaces can be brought up.
    for conf_file in sorted(WG_CONFIG_DIR.glob("*.conf")):
        name = conf_file.stem
        if name in interfaces:
            continue
        if not IFACE_NAME_PATTERN.match(name):
            logger.warning("skipping .conf with invalid interface name: %s", name)
            continue
        interfaces[name] = Interface(name=name, status="down")

    return list(interfaces.values())


async def get_interface(name: str) -> Interface | None:
    stdout, _, rc = await _run(["wg", "show", name, "dump"])
    if rc == 0 and stdout:
        lines = stdout.splitlines()
        iface = _interface_from_dump(name, lines[0].split("\t"))
        iface.num_peers = len(lines) - 1
        return iface

    if _conf_path(name).exists():
        return Interface(name=name, status="down")
    return None


async def update_interface(name: str, update: InterfaceUpdate) -> None:
    args = ["wg", "set", name]
    if update.private_key:
        args += ["private-key", "/dev/stdin"]
    if update.listen_port is not None:
        args += ["listen-port", str(update.listen_port)]
    if update.fw_mark is not None:
        args += ["fwmark", update.fw_mark]
    stdin_data = update.private_key.encode() if update.private_key else None
    logger.info("updating interface %s", name)
    await _check(args, stdin_data=stdin_data)


async def interface_up(name: str) -> None:
    _require_conf(name)
    logger.info("bringing up interface %s", name)
    await _check(["wg-quick", "up", name])


async def interface_down(name: str) -> None:
    _require_conf(name)
    logger.info("bringing down interface %s", name)
    await _check(["wg-quick", "down", name])


async def interface_save(name: str) -> None:
    _require_conf(name)
    logger.info("saving interface %s", name)
    await _check(["wg-quick", "save", name])


# ---------------------------------------------------------------------------
# Peers
# ---------------------------------------------------------------------------


def _parse_peers_dump(lines: list[str]) -> list[Peer]:
    peers: list[Peer] = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        try:
            peers.append(
                Peer(
                    # parts[1] is the preshared key: a secret, never read back.
                    public_key=parts[0],
                    endpoint=parts[2] if parts[2] != "(none)" else None,
                    allowed_ips=parts[3] if parts[3] != "(none)" else None,
                    latest_handshake=int(parts[4]) if parts[4] != "0" else None,
                    transfer_rx=int(parts[5]),
                    transfer_tx=int(parts[6]),
                    persistent_keepalive=int(parts[7]) if parts[7] != "off" else None,
                )
            )
        except (ValueError, IndexError):
            logger.warning("skipping malformed peer dump line: %s", line)
    return peers


async def list_peers(iface: str) -> list[Peer] | None:
    stdout, _, rc = await _run(["wg", "show", iface, "dump"])
    if rc != 0:
        return None
    return _parse_peers_dump(stdout.splitlines()[1:])


async def get_peer(iface: str, public_key: str) -> Peer | None:
    peers = await list_peers(iface)
    if peers is None:
        return None
    return next((p for p in peers if p.public_key == public_key), None)


async def set_peer(
    iface: str,
    public_key: str,
    allowed_ips: str | None = None,
    endpoint: str | None = None,
    preshared_key: str | None = None,
    persistent_keepalive: int | None = None,
) -> None:
    args = ["wg", "set", iface, "peer", public_key]
    if allowed_ips:
        args += ["allowed-ips", allowed_ips]
    if endpoint:
        args += ["endpoint", endpoint]
    if preshared_key:
        args += ["preshared-key", "/dev/stdin"]
    if persistent_keepalive is not None:
        args += ["persistent-keepalive", str(persistent_keepalive)]
    stdin_data = preshared_key.encode() if preshared_key else None
    logger.info("setting peer %s on %s", public_key[:8], iface)
    await _check(args, stdin_data=stdin_data)


async def delete_peer(iface: str, public_key: str) -> None:
    logger.info("deleting peer %s from %s", public_key[:8], iface)
    await _check(["wg", "set", iface, "peer", public_key, "remove"])
