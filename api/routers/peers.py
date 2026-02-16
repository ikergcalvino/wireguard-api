from fastapi import APIRouter, HTTPException

from api.models.peers import PeerCreate, PeerCreateResponse, PeerListResponse, PeerResponse
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


@router.post("", response_model=PeerCreateResponse, status_code=201)
async def create_peer(iface: str, body: PeerCreate):
    try:
        data = await wg.create_peer(iface=iface, allowed_ips=body.allowed_ips)
    except ValueError as e:
        status = 404 if "not found" in str(e) else 409
        raise HTTPException(status_code=status, detail=str(e))
    return data


@router.get("/{public_key}", response_model=PeerResponse)
async def get_peer(iface: str, public_key: str):
    try:
        peer = await wg.get_peer(iface, public_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")
    return peer


@router.delete("/{public_key}", status_code=204)
async def delete_peer(iface: str, public_key: str):
    try:
        deleted = await wg.delete_peer(iface, public_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Peer not found")
