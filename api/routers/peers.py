from fastapi import APIRouter, HTTPException

from api.models.peers import PeerCreate, PeerListResponse, PeerResponse
from api.services import wireguard as wg

router = APIRouter(prefix="/peers", tags=["peers"])


@router.get("", response_model=PeerListResponse)
async def list_peers():
    peers = await wg.list_peers()
    return PeerListResponse(peers=peers, total=len(peers))


@router.get("/{name}", response_model=PeerResponse)
async def get_peer(name: str):
    peer = await wg.get_peer(name)
    if not peer:
        raise HTTPException(status_code=404, detail=f"Peer '{name}' not found")
    return peer


@router.post("", response_model=PeerResponse, status_code=201)
async def create_peer(peer: PeerCreate):
    try:
        data = await wg.create_peer(
            name=peer.name, allowed_ips=peer.allowed_ips, dns=peer.dns
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return PeerResponse(
        name=data["name"],
        public_key=data["public_key"],
        allowed_ips=data["address"],
        enabled=data["enabled"],
    )


@router.delete("/{name}", status_code=204)
async def delete_peer(name: str):
    deleted = await wg.delete_peer(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Peer '{name}' not found")
