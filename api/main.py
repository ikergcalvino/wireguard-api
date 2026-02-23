import logging
from importlib.metadata import version

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from api.config import settings
from api.exceptions import register_exception_handlers
from api.routers import interfaces, peers

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("wireguard-api")

APP_VERSION = version("wireguard-api")

app = FastAPI(
    title="WireGuard API",
    description="REST API to manage WireGuard interfaces and peers on the host.",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: str | None = Security(api_key_header)):
    if not settings.api_key:
        return
    if key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


app.include_router(interfaces.router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(peers.router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])


@app.get("/")
async def root():
    return {"name": "wireguard-api", "version": APP_VERSION}


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
