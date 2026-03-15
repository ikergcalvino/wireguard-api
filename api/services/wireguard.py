from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from api.config import settings
from api.models.interfaces import Interface
from api.models.peers import Peer

logger = logging.getLogger("wireguard-api")

WG_CONFIG_DIR = settings.config_dir
_CMD_TIMEOUT = 30
_create_lock = asyncio.Lock()


async def _run(args: list[str], stdin_data: bytes | None = None) -> tuple[str, str, int]:
    logger.debug("exec: %s", args)
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE if stdin_data else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=stdin_data),
            timeout=_CMD_TIMEOUT,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        logger.error("cmd %s timed out after %ds", args, _CMD_TIMEOUT)
        return "", f"Command timed out after {_CMD_TIMEOUT}s", 1
    out, err, rc = stdout.decode().strip(), stderr.decode().strip(), proc.returncode or 0
    if rc != 0:
        logger.warning("cmd %s failed (rc=%d): %s", args, rc, err)
    return out, err, rc


def _conf_path(name: str) -> Path:
    conf = (WG_CONFIG_DIR / f"{name}.conf").resolve()
    if conf.parent != WG_CONFIG_DIR.resolve():
        raise ValueError(f"Invalid interface name: {name}")
    return conf


def _require_conf(name: str) -> Path:
    conf = _conf_path(name)
    if not conf.exists():
        raise FileNotFoundError(f"Interface '{name}' not found")
    return conf


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------


def _read_conf_address(name: str) -> str | None:
    conf = _conf_path(name)
    if not conf.exists():
        return None
    addresses: list[str] = []
    for line in conf.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped != "[Interface]":
            break
        key, sep, value = stripped.partition("=")
        if sep and key.strip().lower() == "address":
            addresses.append(value.strip())
    return ", ".join(addresses) if addresses else None


async def list_interfaces() -> list[Interface]:
    stdout, _, rc = await _run(["wg", "show", "all", "dump"])
    if rc != 0 or not stdout:
        return []

    interfaces: dict[str, dict] = {}
    for line in stdout.splitlines():
        parts = line.split("\t")
        name = parts[0]
        if len(parts) == 5:
            interfaces[name] = {
                "name": name,
                "public_key": parts[2] if parts[2] != "(none)" else None,
                "listen_port": int(parts[3]) if parts[3].isdigit() else None,
                "fw_mark": parts[4] if parts[4] != "off" else None,
                "num_peers": 0,
                "address": _read_conf_address(name),
            }
        elif len(parts) == 9 and name in interfaces:
            interfaces[name]["num_peers"] += 1

    return [Interface(**data) for data in interfaces.values()]


async def get_interface(name: str) -> Interface | None:
    stdout, _, rc = await _run(["wg", "show", name, "dump"])
    if rc != 0:
        return None

    lines = stdout.splitlines()
    if not lines:
        return None

    # wg show dump: private_key \t public_key \t listen_port \t fwmark
    # parts[0] is private_key — intentionally omitted from response for security
    parts = lines[0].split("\t")
    return Interface(
        name=name,
        public_key=parts[1] if len(parts) > 1 and parts[1] != "(none)" else None,
        listen_port=int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None,
        fw_mark=parts[3] if len(parts) > 3 and parts[3] != "off" else None,
        num_peers=len(lines) - 1,
        address=_read_conf_address(name),
    )


def _build_conf_content(iface: Interface, peers: list[Peer] | None = None) -> bytes:
    lines = ["[Interface]"]
    if iface.address:
        lines.append(f"Address = {iface.address}")
    if iface.private_key:
        lines.append(f"PrivateKey = {iface.private_key}")
    if iface.listen_port is not None:
        lines.append(f"ListenPort = {iface.listen_port}")
    if iface.fw_mark:
        lines.append(f"FwMark = {iface.fw_mark}")
    if iface.dns:
        lines.append(f"DNS = {iface.dns}")
    if iface.mtu is not None:
        lines.append(f"MTU = {iface.mtu}")
    if iface.table:
        lines.append(f"Table = {iface.table}")
    if iface.pre_up:
        lines.append(f"PreUp = {iface.pre_up}")
    if iface.post_up:
        lines.append(f"PostUp = {iface.post_up}")
    if iface.pre_down:
        lines.append(f"PreDown = {iface.pre_down}")
    if iface.post_down:
        lines.append(f"PostDown = {iface.post_down}")
    if iface.save_config is not None:
        lines.append(f"SaveConfig = {'true' if iface.save_config else 'false'}")
    if peers:
        for peer in peers:
            lines.append("")
            lines.append("[Peer]")
            if peer.public_key:
                lines.append(f"PublicKey = {peer.public_key}")
            if peer.preshared_key:
                lines.append(f"PresharedKey = {peer.preshared_key}")
            if peer.allowed_ips:
                lines.append(f"AllowedIPs = {peer.allowed_ips}")
            if peer.endpoint:
                lines.append(f"Endpoint = {peer.endpoint}")
            if peer.persistent_keepalive is not None:
                lines.append(f"PersistentKeepalive = {peer.persistent_keepalive}")
    return ("\n".join(lines) + "\n").encode()


async def create_interface(iface: Interface) -> tuple[str, int]:
    if not iface.private_key:
        raise ValueError("private_key is required to create an interface")
    if not iface.address:
        raise ValueError("address is required to create an interface")

    conf = _conf_path(iface.name)
    content = _build_conf_content(iface)
    async with _create_lock:
        try:
            fd = os.open(str(conf), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.write(fd, content)
            finally:
                os.close(fd)
        except FileExistsError:
            raise FileExistsError(f"Interface '{iface.name}' already exists") from None

        logger.info("creating interface %s", iface.name)
        _, stderr, rc = await _run(["wg-quick", "up", iface.name])
        if rc != 0:
            conf.unlink(missing_ok=True)
    return stderr, rc


async def update_interface(name: str, iface: Interface) -> tuple[str, int]:
    if not iface.private_key:
        raise ValueError("private_key is required")
    if not iface.address:
        raise ValueError("address is required")

    conf = _require_conf(name)
    peers = await list_peers(name)
    content = _build_conf_content(iface, peers=peers)
    conf.write_bytes(content)
    conf.chmod(0o600)

    logger.info("updating interface %s", name)
    _, stderr, rc = await _run(["wg", "syncconf", name, str(conf)])
    return stderr, rc


async def delete_interface(name: str) -> tuple[str, int]:
    conf = _require_conf(name)
    logger.info("deleting interface %s", name)
    _, stderr, rc = await _run(["wg-quick", "down", name])
    if rc != 0:
        return stderr, rc
    conf.unlink(missing_ok=True)
    return "", 0


async def interface_up(name: str) -> tuple[str, int]:
    _require_conf(name)
    logger.info("bringing up interface %s", name)
    _, stderr, rc = await _run(["wg-quick", "up", name])
    return stderr, rc


async def interface_down(name: str) -> tuple[str, int]:
    _require_conf(name)
    logger.info("bringing down interface %s", name)
    _, stderr, rc = await _run(["wg-quick", "down", name])
    return stderr, rc


async def interface_save(name: str) -> tuple[str, int]:
    _require_conf(name)
    logger.info("saving interface %s", name)
    _, stderr, rc = await _run(["wg-quick", "save", name])
    return stderr, rc


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
                    public_key=parts[0],
                    preshared_key=parts[1] if parts[1] != "(none)" else None,
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
) -> tuple[str, int]:
    if not public_key:
        raise ValueError("public_key is required")
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
    _, stderr, rc = await _run(args, stdin_data=stdin_data)
    return stderr, rc


async def delete_peer(iface: str, public_key: str) -> tuple[str, int]:
    logger.info("deleting peer %s from %s", public_key[:8], iface)
    _, stderr, rc = await _run(["wg", "set", iface, "peer", public_key, "remove"])
    return stderr, rc
