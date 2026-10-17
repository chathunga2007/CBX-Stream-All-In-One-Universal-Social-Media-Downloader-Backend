"""Endpoints for multi-item carousel ZIP archiving and media CORS reverse proxying."""

from fastapi import APIRouter, Query, status
from fastapi.responses import StreamingResponse

from app.core.logger import get_logger
from app.schemas.media_schemas import (
    CarouselZipRequest,
    CarouselZipResponse,
    ErrorResponse,
)
from app.services.carousel_service import carousel_service

logger = get_logger(__name__)

router = APIRouter(tags=["Carousel & Gallery Bundler"])


@router.post(
    "/carousel/zip",
    response_model=CarouselZipResponse,
    status_code=status.HTTP_200_OK,
    summary="Package Carousel Items into ZIP",
    description="Download all photo/video slides from a multi-item post (Instagram, Reddit, Pinterest) and bundle into a ZIP archive.",
    responses={
        422: {"model": ErrorResponse, "description": "Failed to bundle carousel items"},
    },
)
async def bundle_carousel(request: CarouselZipRequest) -> CarouselZipResponse:
    """Download and bundle multi-image/video post into a single ZIP file."""
    return await carousel_service.bundle_carousel_zip(
        media_urls=request.media_urls,
        custom_filename=request.custom_filename,
    )


@router.get(
    "/proxy-media",
    summary="Reverse Media Proxy (CORS Bypass)",
    description="Stream hotlink-protected or CORS-blocked images and videos directly from social CDN sources.",
    responses={
        422: {"model": ErrorResponse, "description": "Failed to proxy remote media"},
        200: {"description": "Media stream returned successfully"},
    },
)
async def proxy_media(
    url: str = Query(..., description="Upstream media URL to stream through the proxy")
) -> StreamingResponse:
    """Proxy remote image or video stream to bypass CORS and hotlink restrictions."""
    return await carousel_service.proxy_media_stream(url)
