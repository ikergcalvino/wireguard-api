import asyncio
import ipaddress
import json
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


def _iface_dir(iface: str) -> Path:
    path = Path(settings.WG_CONFIG_DIR) / iface
    path.mkdir(parents=True, exist_ok=True)
    return path


def _iface_db_path(iface: str) -> Path:
    return _iface_dir(iface) / "interface.json"


def _peers_db_path(iface: str) -> Path:
    return _iface_dir(iface) / "peers.json"


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2))


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
    db_path = _iface_db_path(name)
    if db_path.exists():
        raise ValueError(f"Interface '{name}' already exists")

    privkey, pubkey = await _generate_keypair()

    iface_data = {
        "name": name,
        "private_key": privkey,
        "public_key": pubkey,
        "address": address,
        "listen_port": listen_port,
        "post_up": post_up,
        "post_down": post_down,
    }

    conf_path = Path(settings.WG_CONFIG_DIR) / f"{name}.conf"
    conf_path.write_text(
        f"[Interface]\n"
        f"Address = {address}\n"
        f"ListenPort = {listen_port}\n"
        f"PrivateKey = {privkey}\n"
        f"PostUp = {post_up}\n"
        f"PostDown = {post_down}\n"
    )
    conf_path.chmod(0o600)

    _save_json(db_path, iface_data)
    _save_json(_peers_db_path(name), {})

    await _run(f"wg-quick up {name}")

    return {**iface_data, "status": "up", "total_peers": 0, "enabled_peers": 0}


async def list_interfaces() -> list[dict]:
    config_dir = Path(settings.WG_CONFIG_DIR)
    interfaces = []
    for iface_dir in sorted(config_dir.iterdir()):
        if not iface_dir.is_dir():
            continue
        db_path = iface_dir / "interface.json"
        if not db_path.exists():
            continue
        iface = _load_json(db_path)
        name = iface["name"]
        _, _, rc = await _run(f"wg show {name}")
        peers_db = _load_json(_peers_db_path(name))
        interfaces.append({
            "name": name,
            "public_key": iface["public_key"],
            "address": iface["address"],
            "listen_port": iface["listen_port"],
            "status": "up" if rc == 0 else "down",
            "total_peers": len(peers_db),
            "enabled_peers": sum(1 for p in peers_db.values() if p.get("enabled", True)),
        })
    return interfaces


async def get_interface(name: str) -> dict | None:
    db_path = _iface_db_path(name)
    if not db_path.exists():
        return None

    iface = _load_json(db_path)
    stdout, _, rc = await _run(f"wg show {name}")

    transfer = None
    if rc == 0:
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("transfer:"):
                transfer = line.split(":", 1)[1].strip()

    peers_db = _load_json(_peers_db_path(name))
    return {
        "name": name,
        "public_key": iface["public_key"],
        "address": iface["address"],
        "listen_port": iface["listen_port"],
        "status": "up" if rc == 0 else "down",
        "transfer": transfer,
        "total_peers": len(peers_db),
        "enabled_peers": sum(1 for p in peers_db.values() if p.get("enabled", True)),
    }


async def delete_interface(name: str) -> bool:
    db_path = _iface_db_path(name)
    if not db_path.exists():
        return False

    await _run(f"wg-quick down {name}")

    conf_path = Path(settings.WG_CONFIG_DIR) / f"{name}.conf"
    if conf_path.exists():
        conf_path.unlink()

    iface_dir = _iface_dir(name)
    for f in iface_dir.iterdir():
        f.unlink()
    iface_dir.rmdir()

    return True


# ---------------------------------------------------------------------------
# Peers
# ---------------------------------------------------------------------------

def _next_ip(iface: str) -> str:
    iface_data = _load_json(_iface_db_path(iface))
    address = iface_data["address"]
    network = ipaddress.ip_network(address, strict=False)
    server_ip = address.split("/")[0]

    peers_db = _load_json(_peers_db_path(iface))
    used = {server_ip}
    for peer in peers_db.values():
        used.add(peer["address"].split("/")[0])

    for host in network.hosts():
        if str(host) not in used:
            return str(host)
    raise ValueError("No available IPs in subnet")


async def create_peer(iface: str, name: str, allowed_ips: str, dns: str) -> dict:
    if not _iface_db_path(iface).exists():
        raise ValueError(f"Interface '{iface}' not found")

    peers_db = _load_json(_peers_db_path(iface))
    if name in peers_db:
        raise ValueError(f"Peer '{name}' already exists on interface '{iface}'")

    privkey, pubkey = await _generate_keypair()
    address = _next_ip(iface)

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

    await _run(f"wg set {iface} peer {pubkey} allowed-ips {address}/32")
    await _run(f"wg-quick save {iface}")

    peers_db[name] = peer_data
    _save_json(_peers_db_path(iface), peers_db)

    return peer_data


async def list_peers(iface: str) -> list[dict]:
    if not _iface_db_path(iface).exists():
        raise ValueError(f"Interface '{iface}' not found")

    peers_db = _load_json(_peers_db_path(iface))
    runtime = await _get_runtime_info(iface)
    peers = []
    for name, peer in peers_db.items():
        info = runtime.get(peer["public_key"], {})
        peers.append({
            "name": name,
            "public_key": peer["public_key"],
            "allowed_ips": peer["address"],
            "endpoint": info.get("endpoint"),
            "latest_handshake": info.get("latest_handshake"),
            "transfer_rx": info.get("transfer_rx"),
            "transfer_tx": info.get("transfer_tx"),
            "enabled": peer.get("enabled", True),
        })
    return peers


async def get_peer(iface: str, name: str) -> dict | None:
    if not _iface_db_path(iface).exists():
        raise ValueError(f"Interface '{iface}' not found")

    peers_db = _load_json(_peers_db_path(iface))
    peer = peers_db.get(name)
    if not peer:
        return None

    runtime = await _get_runtime_info(iface)
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


async def delete_peer(iface: str, name: str) -> bool:
    if not _iface_db_path(iface).exists():
        raise ValueError(f"Interface '{iface}' not found")

    peers_db = _load_json(_peers_db_path(iface))
    peer = peers_db.pop(name, None)
    if not peer:
        return False

    await _run(f"wg set {iface} peer {peer['public_key']} remove")
    await _run(f"wg-quick save {iface}")

    _save_json(_peers_db_path(iface), peers_db)
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
