import shutil

from fastapi import APIRouter, Depends

from api import __version__
from api.config import settings
from api.dependencies import verify_api_key

router = APIRouter(tags=["system"])


@router.get("", dependencies=[Depends(verify_api_key)])
async def info():
    return {"name": "wireguard-api", "version": __version__}


# Public, so container healthchecks and load balancers need no API key.
@router.get("/health")
async def health():
    checks = {
        "config_dir": "ok" if settings.config_dir.is_dir() else "missing",
        "wg": "ok" if shutil.which("wg") else "missing",
        "wg_quick": "ok" if shutil.which("wg-quick") else "missing",
    }
    ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}
