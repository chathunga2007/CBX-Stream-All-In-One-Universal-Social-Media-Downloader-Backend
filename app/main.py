"""FastAPI Application entry point for CBX-Stream Universal Social Media Downloader Backend."""

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_v1_router, ws_router
from app.core.config import settings
from app.core.exceptions import CBXStreamException
from app.core.logger import get_logger, setup_root_logger
from app.schemas.media_schemas import ErrorResponse
from app.services.cleanup_service import cleanup_service
from app.services.pot_service import pot_service
from app.services.ws_manager import ws_manager

logger = get_logger("cbx_stream.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager coordinating background services and clean shutdown."""
    # Ensure Windows uses ProactorEventLoop where possible for subprocess support
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            logger.debug("Retained default Windows event loop policy.")

    # Startup
    setup_root_logger()
    loop = asyncio.get_running_loop()
    ws_manager.set_loop(loop)

    logger.info("==================================================================")
    logger.info(f" Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f" Temp Storage Dir: {settings.TEMP_DIR.resolve()}")
    logger.info(f" FFmpeg Executable: {settings.FFMPEG_PATH}")
    logger.info(f" API Prefix: {settings.API_V1_PREFIX}")
    logger.info("==================================================================")

    # Start periodic background cleanup worker
    cleanup_service.start()

    # Start background YouTube PO Token generator provider
    pot_service.start()

    yield

    # Shutdown
    logger.info("Shutting down CBX-Stream Backend...")
    await cleanup_service.stop()
    pot_service.stop()
    logger.info("Cleanup worker & POT service stopped. Shutdown complete.")


# Initialize FastAPI Application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Universal, high-performance social media downloader and media streaming backend "
        "supporting 4K DASH merging, precision timestamp clipping, multi-photo carousel ZIP "
        "bundling, ID3 cover art embedding, and real-time WebSocket progress broadcasts."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure Universal Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Global Exception Handlers
# ==============================================================================

@app.exception_handler(CBXStreamException)
async def cbx_stream_exception_handler(request: Request, exc: CBXStreamException) -> JSONResponse:
    """Handle all domain-specific application exceptions with clean structured JSON."""
    logger.warning(f"Domain error [{exc.error_code}] on {request.url.path}: {exc.message}")
    error_payload = ErrorResponse(
        success=False,
        error_code=exc.error_code,
        detail=exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload.model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Format Pydantic schema validation failures into clean JSON responses."""
    errors = exc.errors()
    error_details = []
    for err in errors:
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Validation error")
        error_details.append(f"{loc}: {msg}")

    detail_str = "; ".join(error_details) if error_details else "Invalid request payload."
    logger.warning(f"Validation error on {request.url.path}: {detail_str}")

    error_payload = ErrorResponse(
        success=False,
        error_code="VALIDATION_ERROR",
        detail=detail_str,
    )
    return JSONResponse(
        status_code=422,
        content=error_payload.model_dump(),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard Starlette / FastAPI HTTP exceptions."""
    error_payload = ErrorResponse(
        success=False,
        error_code=f"HTTP_{exc.status_code}",
        detail=str(exc.detail),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload.model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all unhandled exception handler ensuring clean JSON 500 responses."""
    logger.error(f"Unhandled server exception on {request.url.path}: {exc}", exc_info=True)
    error_payload = ErrorResponse(
        success=False,
        error_code="INTERNAL_SERVER_ERROR",
        detail="An internal server error occurred while processing your request.",
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_payload.model_dump(),
    )


# ==============================================================================
# Router Inclusions
# ==============================================================================

# Mount v1 REST endpoints under /api/v1
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

# Mount direct WebSocket routes at root /ws/progress/{task_id} as well
app.include_router(ws_router)


# ==============================================================================
# Root Information Endpoint
# ==============================================================================

@app.get("/", tags=["System Information"])
async def root_index() -> dict:
    """Root metadata endpoint verifying backend availability and API endpoints."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "api_v1_docs": "/docs",
        "health_check": f"{settings.API_V1_PREFIX}/health",
        "supported_platforms": [
            "YouTube (4K Ultra, Shorts, Music)",
            "TikTok (HD No-Watermark)",
            "Instagram (Reels, Posts, Stories, Carousels)",
            "Facebook (Watch, Reels, Video)",
            "Twitter / X (1080p Video, Clips)",
            "Reddit (Video + Audio, Galleries)",
            "Pinterest (High-Res Pins, Idea Pins)",
            "SoundCloud (HQ Audio)",
            "Spotify (Track Metadata)",
            "Vimeo, Threads, Twitch, Bilibili",
            "1000+ Universal Streaming Sites",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
