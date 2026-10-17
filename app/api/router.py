"""Master API router aggregating all v1 REST and WebSocket route modules."""

from fastapi import APIRouter

from app.api.routes_analyze import router as analyze_router
from app.api.routes_download import router as download_router
from app.api.routes_trim import router as trim_router
from app.api.routes_carousel import router as carousel_router
from app.api.routes_system import router as system_router
from app.api.routes_ws import router as ws_router

# Master v1 API Router
api_v1_router = APIRouter()

# Include feature sub-routers
api_v1_router.include_router(analyze_router)
api_v1_router.include_router(download_router)
api_v1_router.include_router(trim_router)
api_v1_router.include_router(carousel_router)
api_v1_router.include_router(system_router)
api_v1_router.include_router(ws_router)

__all__ = ["api_v1_router", "ws_router"]
