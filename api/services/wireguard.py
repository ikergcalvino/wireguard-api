import asyncio
import ipaddress
import re
from pathlib import Path

from api.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run(cmd: str) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode().strip(), stderr.decode().strip(), proc.returncode


async def _generate_keypair() -> tuple[str, str]:
    privkey, _, _ = await _run("wg genkey")
    proc = await asyncio.create_subprocess_shell(
        "wg pubkey",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate(privkey.encode())
    pubkey = stdout.decode().strip()
    return privkey, pubkey


def _conf_path(iface: str) -> Path:
    return Path(settings.WG_CONFIG_DIR) / f"{iface}.conf"


def _parse_conf(iface: str) -> dict | None:
    path = _conf_path(iface)
    if not path.exists():
        return None

    text = path.read_text()
    result = {"interface": {}, "peers": []}

    current = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[Interface]":
            current = result["interface"]
            continue
        if line == "[Peer]":
            current = {}
            result["peers"].append(current)
            continue
        if current is None:
            continue
        match = re.match(r"^(\w+)\s*=\s*(.+)$", line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            current[key] = value

    return result


def _pubkey_from_privkey_sync(privkey: str) -> str:
    import subprocess
    proc = subprocess.run(
        ["wg", "pubkey"],
        input=privkey.encode(),
        capture_output=True,
    )
    return proc.stdout.decode().strip()


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------

async def create_interface(
    name: str,
    address: str,
    listen_port: int,
    post_up: str,
    post_down: str,
) -> dict:
    conf = _conf_path(name)
    if conf.exists():
        raise ValueError(f"Interface '{name}' already exists")

    privkey, pubkey = await _generate_keypair()

    conf.write_text(
        f"[Interface]\n"
        f"Address = {address}\n"
        f"ListenPort = {listen_port}\n"
        f"PrivateKey = {privkey}\n"
        f"PostUp = {post_up}\n"
        f"PostDown = {post_down}\n"
    )
    conf.chmod(0o600)

    await _run(f"wg-quick up {name}")

    return {
        "name": name,
        "public_key": pubkey,
        "address": address,
        "listen_port": listen_port,
        "status": "up",
        "total_peers": 0,
    }


async def list_interfaces() -> list[dict]:
    config_dir = Path(settings.WG_CONFIG_DIR)
    interfaces = []
    for conf_file in sorted(config_dir.glob("*.conf")):
        name = conf_file.stem
        parsed = _parse_conf(name)
        if not parsed:
            continue
        iface = parsed["interface"]
        privkey = iface.get("PrivateKey", "")
        pubkey = _pubkey_from_privkey_sync(privkey) if privkey else ""
        _, _, rc = await _run(f"wg show {name}")
        interfaces.append({
            "name": name,
            "public_key": pubkey,
            "address": iface.get("Address", ""),
            "listen_port": int(iface.get("ListenPort", 0)),
            "status": "up" if rc == 0 else "down",
            "total_peers": len(parsed["peers"]),
        })
    return interfaces


async def get_interface(name: str) -> dict | None:
    parsed = _parse_conf(name)
    if not parsed:
        return None

    iface = parsed["interface"]
    privkey = iface.get("PrivateKey", "")
    pubkey = _pubkey_from_privkey_sync(privkey) if privkey else ""

    stdout, _, rc = await _run(f"wg show {name}")
    transfer = None
    if rc == 0:
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("transfer:"):
                transfer = line.split(":", 1)[1].strip()

    return {
        "name": name,
        "public_key": pubkey,
        "address": iface.get("Address", ""),
        "listen_port": int(iface.get("ListenPort", 0)),
        "status": "up" if rc == 0 else "down",
        "transfer": transfer,
        "total_peers": len(parsed["peers"]),
    }


async def delete_interface(name: str) -> bool:
    conf = _conf_path(name)
    if not conf.exists():
        return False

    await _run(f"wg-quick down {name}")
    conf.unlink()
    return True


# ---------------------------------------------------------------------------
# Peers
# ---------------------------------------------------------------------------

def _next_ip(parsed: dict) -> str:
    address = parsed["interface"].get("Address", "")
    network = ipaddress.ip_network(address, strict=False)
    server_ip = address.split("/")[0]

    used = {server_ip}
    for peer in parsed["peers"]:
        for ip in peer.get("AllowedIPs", "").split(","):
            used.add(ip.strip().split("/")[0])

    for host in network.hosts():
        if str(host) not in used:
            return str(host)
    raise ValueError("No available IPs in subnet")


async def create_peer(iface: str, allowed_ips: str) -> dict:
    parsed = _parse_conf(iface)
    if not parsed:
        raise ValueError(f"Interface '{iface}' not found")

    privkey, pubkey = await _generate_keypair()
    address = _next_ip(parsed)

    if not allowed_ips:
        allowed_ips = f"{address}/32"

    await _run(f"wg set {iface} peer {pubkey} allowed-ips {allowed_ips}")
    await _run(f"wg-quick save {iface}")

    return {
        "public_key": pubkey,
        "private_key": privkey,
        "allowed_ips": allowed_ips,
        "address": f"{address}/32",
    }


async def list_peers(iface: str) -> list[dict]:
    parsed = _parse_conf(iface)
    if not parsed:
        raise ValueError(f"Interface '{iface}' not found")

    runtime = await _get_runtime_info(iface)
    peers = []
    for peer in parsed["peers"]:
        pubkey = peer.get("PublicKey", "")
        info = runtime.get(pubkey, {})
        peers.append({
            "public_key": pubkey,
            "allowed_ips": peer.get("AllowedIPs", ""),
            "endpoint": info.get("endpoint"),
            "latest_handshake": info.get("latest_handshake"),
            "transfer_rx": info.get("transfer_rx"),
            "transfer_tx": info.get("transfer_tx"),
        })
    return peers


async def get_peer(iface: str, public_key: str) -> dict | None:
    parsed = _parse_conf(iface)
    if not parsed:
        raise ValueError(f"Interface '{iface}' not found")

    peer = next((p for p in parsed["peers"] if p.get("PublicKey") == public_key), None)
    if not peer:
        return None

    runtime = await _get_runtime_info(iface)
    info = runtime.get(public_key, {})
    return {
        "public_key": public_key,
        "allowed_ips": peer.get("AllowedIPs", ""),
        "endpoint": info.get("endpoint"),
        "latest_handshake": info.get("latest_handshake"),
        "transfer_rx": info.get("transfer_rx"),
        "transfer_tx": info.get("transfer_tx"),
    }


async def delete_peer(iface: str, public_key: str) -> bool:
    parsed = _parse_conf(iface)
    if not parsed:
        raise ValueError(f"Interface '{iface}' not found")

    peer = next((p for p in parsed["peers"] if p.get("PublicKey") == public_key), None)
    if not peer:
        return False

    await _run(f"wg set {iface} peer {public_key} remove")
    await _run(f"wg-quick save {iface}")
    return True


async def _get_runtime_info(iface: str) -> dict:
    stdout, _, rc = await _run(f"wg show {iface} dump")
    if rc != 0:
        return {}

    peers = {}
    lines = stdout.splitlines()
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        pubkey = parts[0]
        peers[pubkey] = {
            "endpoint": parts[2] if parts[2] != "(none)" else None,
            "latest_handshake": parts[4] if parts[4] != "0" else None,
            "transfer_rx": parts[5],
            "transfer_tx": parts[6],
        }
    return peers
