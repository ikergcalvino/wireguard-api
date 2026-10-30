import asyncio
import logging
import os
from pathlib import Path

from api.config import settings
from api.models import IFACE_NAME_PATTERN
from api.models.interfaces import Interface, InterfaceUpdate
from api.models.peers import Peer, PeerCreate, PeerUpdate

logger = logging.getLogger("wireguard-api")

WG_CONFIG_DIR = settings.config_dir
_CMD_TIMEOUT = 30

# Placeholder in a command's arguments for the path of the secret passed to _run().
SECRET_ARG = "<secret>"  # noqa: S105 - a placeholder, not a secret

# wg-quick up/down/save on the same interface must not overlap: concurrent saves
# share a temporary file, and up/down race each other. Locks live in this process,
# so the API must run with a single worker.
_lifecycle_locks: dict[str, asyncio.Lock] = {}


class InterfaceNotFound(Exception):
    """The interface has no config file, so wg-quick cannot manage it."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Interface '{name}' not found")


class WireGuardError(Exception):
    """A wg or wg-quick command failed. The message is its error output."""


class WireGuardUnavailable(Exception):
    """A wg or wg-quick command could not be executed at all."""


async def _run(args: list[str], secret: str | None = None) -> tuple[str, str, int]:
    """Run a command without a shell. A secret is written to a pipe and passed to the
    command as a /dev/fd/N path wherever SECRET_ARG appears in args, so it never shows
    in the process list and never touches disk."""
    read_fd: int | None = None
    if secret is not None:
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, secret.encode())  # a key is 44 bytes, far below the pipe buffer
        finally:
            os.close(write_fd)
        args = [f"/dev/fd/{read_fd}" if arg == SECRET_ARG else arg for arg in args]
    logger.debug("exec: %s", args)
    try:
        # Not stdin: under uvloop, writing to the stdin of a command that reads
        # /dev/stdin itself (as wg does) fails with "the handler is closed".
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            pass_fds=(read_fd,) if read_fd is not None else (),
        )
    except OSError as exc:
        logger.error("cannot execute %s: %s", args[0], exc)
        raise WireGuardUnavailable(f"Cannot execute {args[0]}: {exc.strerror}") from exc
    finally:
        if read_fd is not None:
            os.close(read_fd)
    try:
        async with asyncio.timeout(_CMD_TIMEOUT):
            stdout, stderr = await proc.communicate()
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


async def _check(args: list[str], secret: str | None = None) -> str:
    """Run a command and return its output, raising WireGuardError if it fails."""
    out, err, rc = await _run(args, secret=secret)
    if rc != 0:
        raise WireGuardError(err or f"{args[0]} exited with status {rc}")
    return out


def _conf_path(name: str) -> Path:
    # The name pattern allows no '/', so the path cannot leave the config directory.
    # The file itself may be a symlink, as wg-quick allows.
    if not IFACE_NAME_PATTERN.match(name):
        raise ValueError(f"Invalid interface name: {name}")
    return WG_CONFIG_DIR / f"{name}.conf"


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
        args += ["private-key", SECRET_ARG]
    if update.listen_port is not None:
        args += ["listen-port", str(update.listen_port)]
    if update.fw_mark is not None:
        args += ["fwmark", update.fw_mark]
    logger.info("updating interface %s", name)
    await _check(args, secret=update.private_key)


async def _wg_quick(action: str, name: str) -> None:
    _require_conf(name)
    async with _lifecycle_locks.setdefault(name, asyncio.Lock()):
        logger.info("wg-quick %s %s", action, name)
        await _check(["wg-quick", action, name])


async def interface_up(name: str) -> None:
    await _wg_quick("up", name)


async def interface_down(name: str) -> None:
    await _wg_quick("down", name)


async def interface_save(name: str) -> None:
    await _wg_quick("save", name)


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


async def set_peer(iface: str, public_key: str, peer: PeerCreate | PeerUpdate) -> None:
    """Create or update a peer. Fields left as None are not changed."""
    args = ["wg", "set", iface, "peer", public_key]
    if peer.allowed_ips:
        args += ["allowed-ips", peer.allowed_ips]
    if peer.endpoint:
        args += ["endpoint", peer.endpoint]
    if peer.preshared_key:
        args += ["preshared-key", SECRET_ARG]
    if peer.persistent_keepalive is not None:
        args += ["persistent-keepalive", str(peer.persistent_keepalive)]
    logger.info("setting peer %s on %s", public_key[:8], iface)
    await _check(args, secret=peer.preshared_key)


async def delete_peer(iface: str, public_key: str) -> None:
    logger.info("deleting peer %s from %s", public_key[:8], iface)
    await _check(["wg", "set", iface, "peer", public_key, "remove"])
