from fastapi import APIRouter, HTTPException

from api.models.interfaces import Interface, InterfaceUpdate
from api.routers import IfaceName
from api.services import wireguard as wg

router = APIRouter(prefix="/interfaces", tags=["interfaces"])


@router.get("", response_model=list[Interface])
async def list_interfaces():
    return await wg.list_interfaces()


@router.get("/{name}", response_model=Interface)
async def get_interface(name: IfaceName):
    data = await wg.get_interface(name)
    if not data:
        raise HTTPException(status_code=404, detail=f"Interface '{name}' not found")
    return data


@router.patch("/{name}", response_model=Interface)
async def update_interface(name: IfaceName, body: InterfaceUpdate):
    await wg.update_interface(name, body)
    result = await wg.get_interface(name)
    if not result:
        raise HTTPException(status_code=500, detail="Interface updated but could not be retrieved")
    return result


@router.post("/{name}/up")
async def interface_up(name: IfaceName):
    await wg.interface_up(name)
    return {"status": "up", "interface": name}


@router.post("/{name}/down")
async def interface_down(name: IfaceName):
    await wg.interface_down(name)
    return {"status": "down", "interface": name}


@router.post("/{name}/save")
async def interface_save(name: IfaceName):
    await wg.interface_save(name)
    return {"status": "saved", "interface": name}
