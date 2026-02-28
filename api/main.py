import logging
import shutil
from importlib.metadata import version

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.dependencies import verify_api_key
from api.exceptions import register_exception_handlers
from api.routers import interfaces, peers

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("wireguard-api")

API_VERSION = version("wireguard-api")

app = FastAPI(
    title="WireGuard API",
    description="REST API to manage WireGuard interfaces and peers on the host.",
    version=API_VERSION,
    openapi_tags=[
        {"name": "interfaces", "description": "Manage WireGuard interfaces"},
        {"name": "peers", "description": "Manage peers on WireGuard interfaces"},
    ],
)

cors_origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type"],
)

register_exception_handlers(app)

app.include_router(interfaces.router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(peers.router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])


@app.get("/api/v1", dependencies=[Depends(verify_api_key)])
async def root():
    return {"name": "wireguard-api", "version": API_VERSION}


@app.get("/api/v1/health")
async def health():
    checks: dict[str, str] = {}
    checks["config_dir"] = "ok" if settings.config_dir.is_dir() else "missing"
    checks["wg"] = "ok" if shutil.which("wg") else "missing"
    checks["wg_quick"] = "ok" if shutil.which("wg-quick") else "missing"
    ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}
