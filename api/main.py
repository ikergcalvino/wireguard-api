import logging
import os

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from api.routers import interfaces, peers

LOG_LEVEL = os.getenv("WG_LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("wireguard-api")

API_KEY = os.getenv("WG_API_KEY", "")
CORS_ORIGINS = os.getenv("WG_CORS_ORIGINS", "*")

app = FastAPI(
    title="WireGuard API",
    description="Wrapper mínimo sobre wg/wg-quick",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: str | None = Security(api_key_header)):
    if not API_KEY:
        return
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


app.include_router(interfaces.router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(peers.router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])


@app.get("/")
async def root():
    return {"name": "wireguard-api", "version": "0.1.0"}


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
