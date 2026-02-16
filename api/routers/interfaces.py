from fastapi import APIRouter, HTTPException

from api.models.interfaces import (
    InterfaceCreate,
    InterfaceDetailResponse,
    InterfaceListResponse,
    InterfaceResponse,
)
from api.services import wireguard as wg

router = APIRouter(prefix="/interfaces", tags=["interfaces"])


@router.get("", response_model=InterfaceListResponse)
async def list_interfaces():
    interfaces = await wg.list_interfaces()
    return InterfaceListResponse(interfaces=interfaces, total=len(interfaces))


@router.post("", response_model=InterfaceResponse, status_code=201)
async def create_interface(body: InterfaceCreate):
    try:
        data = await wg.create_interface(
            name=body.name,
            address=body.address,
            listen_port=body.listen_port,
            post_up=body.post_up,
            post_down=body.post_down,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return data


@router.get("/{name}", response_model=InterfaceDetailResponse)
async def get_interface(name: str):
    iface = await wg.get_interface(name)
    if not iface:
        raise HTTPException(status_code=404, detail=f"Interface '{name}' not found")
    return iface


@router.delete("/{name}", status_code=204)
async def delete_interface(name: str):
    deleted = await wg.delete_interface(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Interface '{name}' not found")
