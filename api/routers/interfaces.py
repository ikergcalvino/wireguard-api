from fastapi import APIRouter, HTTPException

from api.models.interfaces import Interface
from api.services import wireguard as wg

router = APIRouter(prefix="/interfaces", tags=["interfaces"])


@router.get("", response_model=list[Interface])
async def list_interfaces():
    return await wg.list_interfaces()


@router.post("", response_model=Interface, status_code=201)
async def create_interface(body: Interface):
    if not body.address or not body.private_key:
        raise HTTPException(
            status_code=422,
            detail="address and private_key are required to create an interface",
        )
    try:
        stderr, rc = await wg.create_interface(
            name=body.name,
            address=body.address,
            listen_port=body.listen_port or 51820,
            private_key=body.private_key,
            post_up=body.post_up,
            post_down=body.post_down,
        )
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    data = await wg.get_interface(body.name)
    return data


@router.get("/{name}", response_model=Interface)
async def get_interface(name: str):
    data = await wg.get_interface(name)
    if not data:
        raise HTTPException(status_code=404, detail=f"Interface '{name}' not found")
    return data


@router.delete("/{name}", status_code=204)
async def delete_interface(name: str):
    try:
        stderr, rc = await wg.delete_interface(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{name}/up")
async def interface_up(name: str):
    stderr, rc = await wg.interface_up(name)
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    return {"status": "up", "interface": name}


@router.post("/{name}/down")
async def interface_down(name: str):
    stderr, rc = await wg.interface_down(name)
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    return {"status": "down", "interface": name}


@router.post("/{name}/save")
async def interface_save(name: str):
    stderr, rc = await wg.interface_save(name)
    if rc != 0:
        raise HTTPException(status_code=400, detail=stderr)
    return {"status": "saved", "interface": name}
