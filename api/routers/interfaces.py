from fastapi import APIRouter, HTTPException

from api.models.interfaces import Interface
from api.routers import IfaceName
from api.services import wireguard as wg

router = APIRouter(prefix="/interfaces", tags=["interfaces"])


@router.get("", response_model=list[Interface])
async def list_interfaces():
    return await wg.list_interfaces()


@router.post("", response_model=Interface, status_code=201)
async def create_interface(body: Interface):
    stderr, rc = await wg.create_interface(body)
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    return await wg.get_interface(body.name)


@router.get("/{name}", response_model=Interface)
async def get_interface(name: IfaceName):
    data = await wg.get_interface(name)
    if not data:
        raise HTTPException(status_code=404, detail=f"Interface '{name}' not found")
    return data


@router.put("/{name}", response_model=Interface)
async def update_interface(name: IfaceName, body: Interface):
    if body.name != name:
        raise HTTPException(status_code=422, detail="Body name does not match URL name")
    stderr, rc = await wg.update_interface(name, body)
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    return await wg.get_interface(name) or body


@router.delete("/{name}", status_code=204)
async def delete_interface(name: IfaceName):
    stderr, rc = await wg.delete_interface(name)
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)


@router.post("/{name}/up")
async def interface_up(name: IfaceName):
    stderr, rc = await wg.interface_up(name)
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    return {"status": "up", "interface": name}


@router.post("/{name}/down")
async def interface_down(name: IfaceName):
    stderr, rc = await wg.interface_down(name)
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    return {"status": "down", "interface": name}


@router.post("/{name}/save")
async def interface_save(name: IfaceName):
    stderr, rc = await wg.interface_save(name)
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    return {"status": "saved", "interface": name}
