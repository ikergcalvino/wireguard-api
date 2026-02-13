from fastapi import APIRouter

from api.services import wireguard as wg

router = APIRouter(prefix="/server", tags=["server"])


@router.get("/status")
async def server_status():
    return await wg.get_server_status()


@router.get("/health")
async def health():
    return {"status": "ok"}
