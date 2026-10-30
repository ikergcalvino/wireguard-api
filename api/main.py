from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import __version__
from api.config import settings
from api.dependencies import verify_api_key
from api.exceptions import register_exception_handlers
from api.logging import setup_logging
from api.routers import interfaces, peers, system

setup_logging()

app = FastAPI(
    title="WireGuard API",
    description="REST API to manage WireGuard interfaces and peers on the host.",
    version=__version__,
    openapi_tags=[
        {"name": "interfaces", "description": "Manage WireGuard interfaces"},
        {"name": "peers", "description": "Manage peers on WireGuard interfaces"},
        {"name": "system", "description": "API information and health"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials="*" not in settings.cors_origin_list,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type"],
)

register_exception_handlers(app)

# Routes have no prefix: a reverse proxy publishes the API under a path such as /api/v1
# and strips it, and UVICORN_ROOT_PATH tells the app so that /docs builds the right URLs.
# The system router decides per route: the health check is public.
app.include_router(system.router)
app.include_router(interfaces.router, dependencies=[Depends(verify_api_key)])
app.include_router(peers.router, dependencies=[Depends(verify_api_key)])
