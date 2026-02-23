import asyncio
import logging

from api.config import settings

logger = logging.getLogger("wireguard-api")

WG_CONFIG_DIR = settings.config_dir


async def _run(args: list[str], stdin_data: bytes | None = None) -> tuple[str, str, int]:
    logger.debug("exec: %s", args)
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE if stdin_data else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(input=stdin_data)
    out, err, rc = stdout.decode().strip(), stderr.decode().strip(), proc.returncode or 0
    if rc != 0:
        logger.warning("cmd %s failed (rc=%d): %s", args, rc, err)
    return out, err, rc


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------


async def create_interface(
    name: str,
    address: str,
    listen_port: int,
    private_key: str,
    post_up: str | None = None,
    post_down: str | None = None,
) -> tuple[str, int]:
    conf = WG_CONFIG_DIR / f"{name}.conf"
    if conf.exists():
        raise FileExistsError(f"Interface '{name}' already exists")

    lines = [
        "[Interface]",
        f"Address = {address}",
        f"ListenPort = {listen_port}",
        f"PrivateKey = {private_key}",
    ]
    if post_up:
        lines.append(f"PostUp = {post_up}")
    if post_down:
        lines.append(f"PostDown = {post_down}")

    conf.write_text("\n".join(lines) + "\n")
    conf.chmod(0o600)

    logger.info("creating interface %s", name)
    _, stderr, rc = await _run(["wg-quick", "up", name])
    return stderr, rc


async def delete_interface(name: str) -> tuple[str, int]:
    conf = WG_CONFIG_DIR / f"{name}.conf"
    if not conf.exists():
        raise FileNotFoundError(f"Interface '{name}' not found")

    logger.info("deleting interface %s", name)
    _, stderr, rc = await _run(["wg-quick", "down", name])
    conf.unlink(missing_ok=True)
    return stderr, rc


async def interface_up(name: str) -> tuple[str, int]:
    logger.info("bringing up interface %s", name)
    _, stderr, rc = await _run(["wg-quick", "up", name])
    return stderr, rc


async def interface_down(name: str) -> tuple[str, int]:
    logger.info("bringing down interface %s", name)
    _, stderr, rc = await _run(["wg-quick", "down", name])
    return stderr, rc


async def interface_save(name: str) -> tuple[str, int]:
    logger.info("saving interface %s", name)
    _, stderr, rc = await _run(["wg-quick", "save", name])
    return stderr, rc


async def list_interfaces() -> list[dict]:
    stdout, _, rc = await _run(["wg", "show", "interfaces"])
    if rc != 0 or not stdout:
        return []

    results = []
    for name in stdout.split():
        data = await get_interface(name)
        if data:
            results.append(data)
    return results


async def get_interface(name: str) -> dict | None:
    stdout, _, rc = await _run(["wg", "show", name, "dump"])
    if rc != 0:
        return None

    lines = stdout.splitlines()
    if not lines:
        return None

    parts = lines[0].split("\t")
    return {
        "name": name,
        "public_key": parts[1] if len(parts) > 1 else None,
        "listen_port": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None,
        "fwmark": parts[3] if len(parts) > 3 and parts[3] != "off" else None,
        "num_peers": len(lines) - 1,
    }


# ---------------------------------------------------------------------------
# Peers
# ---------------------------------------------------------------------------


async def create_peer(
    iface: str,
    public_key: str,
    allowed_ips: str,
    endpoint: str | None = None,
    preshared_key: str | None = None,
    persistent_keepalive: int | None = None,
) -> tuple[str, int]:
    args = ["wg", "set", iface, "peer", public_key, "allowed-ips", allowed_ips]
    if endpoint:
        args += ["endpoint", endpoint]
    if preshared_key:
        args += ["preshared-key", "/dev/stdin"]
    if persistent_keepalive is not None:
        args += ["persistent-keepalive", str(persistent_keepalive)]
    stdin_data = preshared_key.encode() if preshared_key else None
    logger.info("creating peer %s on %s", public_key[:8], iface)
    _, stderr, rc = await _run(args, stdin_data=stdin_data)
    return stderr, rc


async def update_peer(
    iface: str,
    public_key: str,
    allowed_ips: str | None = None,
    endpoint: str | None = None,
    persistent_keepalive: int | None = None,
) -> tuple[str, int]:
    args = ["wg", "set", iface, "peer", public_key]
    if allowed_ips:
        args += ["allowed-ips", allowed_ips]
    if endpoint:
        args += ["endpoint", endpoint]
    if persistent_keepalive is not None:
        args += ["persistent-keepalive", str(persistent_keepalive)]
    logger.info("updating peer %s on %s", public_key[:8], iface)
    _, stderr, rc = await _run(args)
    return stderr, rc


async def delete_peer(iface: str, public_key: str) -> tuple[str, int]:
    logger.info("deleting peer %s from %s", public_key[:8], iface)
    _, stderr, rc = await _run(["wg", "set", iface, "peer", public_key, "remove"])
    return stderr, rc


async def list_peers(iface: str) -> list[dict] | None:
    stdout, _, rc = await _run(["wg", "show", iface, "dump"])
    if rc != 0:
        return None
    return _parse_peers_dump(stdout.splitlines()[1:])


async def get_peer(iface: str, public_key: str) -> dict | None:
    peers = await list_peers(iface)
    if peers is None:
        return None
    return next((p for p in peers if p["public_key"] == public_key), None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_peers_dump(lines: list[str]) -> list[dict]:
    peers = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        peers.append(
            {
                "public_key": parts[0],
                "preshared_key": parts[1] if parts[1] != "(none)" else None,
                "endpoint": parts[2] if parts[2] != "(none)" else None,
                "allowed_ips": parts[3] if parts[3] != "(none)" else None,
                "latest_handshake": int(parts[4]) if parts[4] != "0" else None,
                "transfer_rx": int(parts[5]),
                "transfer_tx": int(parts[6]),
                "persistent_keepalive": int(parts[7]) if parts[7] != "off" else None,
            }
        )
    return peers
