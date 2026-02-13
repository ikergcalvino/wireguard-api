import asyncio
import ipaddress
import json
import os
from pathlib import Path

from api.config import settings


async def _run(cmd: str) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode().strip(), stderr.decode().strip(), proc.returncode


def _peers_db_path() -> Path:
    return Path(settings.WG_CONFIG_DIR) / "peers.json"


def _load_peers_db() -> dict:
    path = _peers_db_path()
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save_peers_db(db: dict) -> None:
    _peers_db_path().write_text(json.dumps(db, indent=2))


def _next_ip() -> str:
    db = _load_peers_db()
    network = ipaddress.ip_network(settings.WG_SUBNET, strict=False)
    used = {settings.WG_SERVER_IP}
    for peer in db.values():
        used.add(peer["address"].split("/")[0])
    for host in network.hosts():
        if str(host) not in used:
            return str(host)
    raise ValueError("No available IPs in subnet")


async def generate_keypair() -> tuple[str, str]:
    privkey, _, _ = await _run("wg genkey")
    proc = await asyncio.create_subprocess_shell(
        "wg pubkey",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate(privkey.encode())
    pubkey = stdout.decode().strip()
    return privkey, pubkey


async def create_peer(name: str, allowed_ips: str, dns: str) -> dict:
    db = _load_peers_db()
    if name in db:
        raise ValueError(f"Peer '{name}' already exists")

    privkey, pubkey = await generate_keypair()
    address = _next_ip()

    if not allowed_ips:
        allowed_ips = "0.0.0.0/0"

    peer_data = {
        "name": name,
        "private_key": privkey,
        "public_key": pubkey,
        "address": f"{address}/32",
        "allowed_ips": allowed_ips,
        "dns": dns,
        "enabled": True,
    }

    await _run(
        f"wg set {settings.WG_INTERFACE} peer {pubkey} allowed-ips {address}/32"
    )
    await _sync_config()

    db[name] = peer_data
    _save_peers_db(db)

    return peer_data


async def list_peers() -> list[dict]:
    db = _load_peers_db()
    runtime = await _get_runtime_info()
    peers = []
    for name, peer in db.items():
        info = runtime.get(peer["public_key"], {})
        peers.append(
            {
                "name": name,
                "public_key": peer["public_key"],
                "allowed_ips": peer["address"],
                "endpoint": info.get("endpoint"),
                "latest_handshake": info.get("latest_handshake"),
                "transfer_rx": info.get("transfer_rx"),
                "transfer_tx": info.get("transfer_tx"),
                "enabled": peer.get("enabled", True),
            }
        )
    return peers


async def get_peer(name: str) -> dict | None:
    db = _load_peers_db()
    peer = db.get(name)
    if not peer:
        return None
    runtime = await _get_runtime_info()
    info = runtime.get(peer["public_key"], {})
    return {
        "name": name,
        "public_key": peer["public_key"],
        "allowed_ips": peer["address"],
        "endpoint": info.get("endpoint"),
        "latest_handshake": info.get("latest_handshake"),
        "transfer_rx": info.get("transfer_rx"),
        "transfer_tx": info.get("transfer_tx"),
        "enabled": peer.get("enabled", True),
    }


async def delete_peer(name: str) -> bool:
    db = _load_peers_db()
    peer = db.pop(name, None)
    if not peer:
        return False
    await _run(f"wg set {settings.WG_INTERFACE} peer {peer['public_key']} remove")
    await _sync_config()
    _save_peers_db(db)
    return True


async def get_server_status() -> dict:
    stdout, _, rc = await _run(f"wg show {settings.WG_INTERFACE}")
    if rc != 0:
        return {"status": "down", "interface": settings.WG_INTERFACE}

    info: dict = {"status": "up", "interface": settings.WG_INTERFACE}
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("public key:"):
            info["public_key"] = line.split(":", 1)[1].strip()
        elif line.startswith("listening port:"):
            info["listening_port"] = line.split(":", 1)[1].strip()
        elif line.startswith("transfer:"):
            info["transfer"] = line.split(":", 1)[1].strip()

    db = _load_peers_db()
    info["total_peers"] = len(db)
    info["enabled_peers"] = sum(1 for p in db.values() if p.get("enabled", True))

    return info


async def _get_runtime_info() -> dict:
    stdout, _, rc = await _run(f"wg show {settings.WG_INTERFACE} dump")
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


async def _sync_config() -> None:
    config_path = os.path.join(
        settings.WG_CONFIG_DIR, f"{settings.WG_INTERFACE}.conf"
    )
    await _run(f"wg-quick save {settings.WG_INTERFACE}")
