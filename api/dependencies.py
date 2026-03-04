import hmac

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from api.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: str | None = Security(api_key_header)) -> None:
    if not settings.api_key:
        return
    if not key or not hmac.compare_digest(key, settings.api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")
