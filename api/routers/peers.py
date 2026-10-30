from fastapi import APIRouter, HTTPException

from api.models.peers import Peer, PeerCreate, PeerUpdate
from api.routers import IfaceName, WgKey
from api.services import wireguard as wg

router = APIRouter(
    prefix="/interfaces/{iface}/peers",
    tags=["peers"],
)


@router.get("")
async def list_peers(iface: IfaceName) -> list[Peer]:
    return await wg.list_peers(iface)


@router.post("", status_code=201)
async def create_peer(iface: IfaceName, body: PeerCreate) -> Peer:
    await wg.set_peer(iface, body.public_key, body)
    return await _get_peer_after_change(iface, body.public_key)


# Public keys are base64 and often contain '/', so the key segment uses the
# path converter; WgKey still validates the whole value.
@router.get("/{public_key:path}")
async def get_peer(iface: IfaceName, public_key: WgKey) -> Peer:
    peer = await wg.get_peer(iface, public_key)
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")
    return peer


@router.put("/{public_key:path}")
async def update_peer(iface: IfaceName, public_key: WgKey, body: PeerUpdate) -> Peer:
    await wg.set_peer(iface, public_key, body)
    return await _get_peer_after_change(iface, public_key)


@router.delete("/{public_key:path}", status_code=204)
async def delete_peer(iface: IfaceName, public_key: WgKey) -> None:
    await wg.delete_peer(iface, public_key)


async def _get_peer_after_change(iface: str, public_key: str) -> Peer:
    peer = await wg.get_peer(iface, public_key)
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found after operation")
    return peer
