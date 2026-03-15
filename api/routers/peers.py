from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from api.models.peers import Peer
from api.routers import IfaceName, WgKey
from api.services import wireguard as wg

router = APIRouter(
    prefix="/interfaces/{iface}/peers",
    tags=["peers"],
)


@router.get("", response_model=list[Peer])
async def list_peers(iface: IfaceName):
    peers = await wg.list_peers(iface)
    if peers is None:
        raise HTTPException(status_code=404, detail=f"Interface '{iface}' not found")
    return peers


@router.post("", response_model=Peer, status_code=201)
async def create_peer(iface: IfaceName, body: Peer):
    if not body.public_key:
        raise HTTPException(status_code=422, detail="public_key is required")
    if not body.allowed_ips:
        raise HTTPException(status_code=422, detail="allowed_ips is required")
    stderr, rc, saved = await wg.set_peer(
        iface=iface,
        public_key=body.public_key,
        allowed_ips=body.allowed_ips,
        endpoint=body.endpoint,
        preshared_key=body.preshared_key,
        persistent_keepalive=body.persistent_keepalive,
    )
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    peer = await wg.get_peer(iface, body.public_key)
    return _peer_response(peer, saved, status_code=201)


@router.get("/{public_key}", response_model=Peer)
async def get_peer(iface: IfaceName, public_key: WgKey):
    peer = await wg.get_peer(iface, public_key)
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")
    return peer


@router.put("/{public_key}", response_model=Peer)
async def update_peer(iface: IfaceName, public_key: WgKey, body: Peer):
    stderr, rc, saved = await wg.set_peer(
        iface=iface,
        public_key=public_key,
        allowed_ips=body.allowed_ips,
        endpoint=body.endpoint,
        preshared_key=body.preshared_key,
        persistent_keepalive=body.persistent_keepalive,
    )
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    peer = await wg.get_peer(iface, public_key)
    return _peer_response(peer, saved)


@router.delete("/{public_key}", status_code=204)
async def delete_peer(iface: IfaceName, public_key: WgKey):
    stderr, rc, saved = await wg.delete_peer(iface, public_key)
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    if not saved:
        return JSONResponse(content=None, status_code=204, headers={"X-Save-Warning": "Config not persisted to disk"})


def _peer_response(peer: Peer | None, saved: bool, status_code: int = 200) -> JSONResponse:
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found after operation")
    headers = {} if saved else {"X-Save-Warning": "Config not persisted to disk"}
    return JSONResponse(
        content=peer.model_dump(mode="json"),
        status_code=status_code,
        headers=headers,
    )
