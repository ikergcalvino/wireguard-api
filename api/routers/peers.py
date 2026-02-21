from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from api.models.peers import Peer
from api.services import wireguard as wg

router = APIRouter(
    prefix="/interfaces/{iface}/peers",
    tags=["peers"],
)

IfaceName = Annotated[str, Path(pattern=r"^[a-zA-Z0-9_-]{1,15}$")]
WgKey = Annotated[str, Path(pattern=r"^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=?$")]


@router.get("", response_model=list[Peer])
async def list_peers(iface: IfaceName):
    peers = await wg.list_peers(iface)
    if peers is None:
        raise HTTPException(status_code=404, detail=f"Interface '{iface}' not found")
    return peers


@router.post("", response_model=Peer, status_code=201)
async def create_peer(iface: IfaceName, body: Peer):
    if not body.allowed_ips:
        raise HTTPException(status_code=422, detail="allowed_ips is required")
    stderr, rc = await wg.create_peer(
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
    return peer


@router.get("/{public_key}", response_model=Peer)
async def get_peer(iface: IfaceName, public_key: WgKey):
    peer = await wg.get_peer(iface, public_key)
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")
    return peer


@router.put("/{public_key}", response_model=Peer)
async def update_peer(iface: IfaceName, public_key: WgKey, body: Peer):
    stderr, rc = await wg.update_peer(
        iface=iface,
        public_key=public_key,
        allowed_ips=body.allowed_ips,
        endpoint=body.endpoint,
        persistent_keepalive=body.persistent_keepalive,
    )
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    peer = await wg.get_peer(iface, public_key)
    return peer


@router.delete("/{public_key}", status_code=204)
async def delete_peer(iface: IfaceName, public_key: WgKey):
    stderr, rc = await wg.delete_peer(iface, public_key)
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
