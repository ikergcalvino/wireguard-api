from fastapi import APIRouter, HTTPException

from api.models.peers import PeerCreate, PeerListResponse, PeerResponse
from api.services import wireguard as wg

router = APIRouter(
    prefix="/interfaces/{iface}/peers",
    tags=["peers"],
)


@router.get("", response_model=PeerListResponse)
async def list_peers(iface: str):
    try:
        peers = await wg.list_peers(iface)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return PeerListResponse(peers=peers, total=len(peers))


@router.post("", response_model=PeerResponse, status_code=201)
async def create_peer(iface: str, body: PeerCreate):
    try:
        data = await wg.create_peer(
            iface=iface, name=body.name, allowed_ips=body.allowed_ips, dns=body.dns
        )
    except ValueError as e:
        status = 404 if "not found" in str(e) else 409
        raise HTTPException(status_code=status, detail=str(e))
    return PeerResponse(
        name=data["name"],
        public_key=data["public_key"],
        allowed_ips=data["address"],
        enabled=data["enabled"],
    )


@router.get("/{name}", response_model=PeerResponse)
async def get_peer(iface: str, name: str):
    try:
        peer = await wg.get_peer(iface, name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not peer:
        raise HTTPException(status_code=404, detail=f"Peer '{name}' not found")
    return peer


@router.delete("/{name}", status_code=204)
async def delete_peer(iface: str, name: str):
    try:
        deleted = await wg.delete_peer(iface, name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Peer '{name}' not found")
