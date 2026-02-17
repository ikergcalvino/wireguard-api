from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader

from api.config import API_KEY
from api.routers import interfaces, peers

app = FastAPI(
    title="WireGuard API",
    description="Wrapper mínimo sobre wg/wg-quick",
    version="0.1.0",
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
