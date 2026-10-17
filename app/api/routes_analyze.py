"""Endpoints for single URL and batch media metadata analysis."""

from fastapi import APIRouter, HTTPException, status
from app.core.exceptions import MediaExtractionError
from app.core.logger import get_logger
from app.schemas.media_schemas import (
    MediaAnalyzeRequest,
    MediaAnalyzeResponse,
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    ErrorResponse,
)
from app.services.extractor_service import extractor_service
from app.services.batch_service import batch_service

logger = get_logger(__name__)

router = APIRouter(tags=["Media Analysis"])


@router.post(
    "/analyze",
    response_model=MediaAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Media URL",
    description="Extract deep metadata, audio/video stream formats, and Chameleon Glass UI theme for any media link.",
    responses={
        422: {"model": ErrorResponse, "description": "Extraction failed"},
        400: {"model": ErrorResponse, "description": "Invalid URL"},
    },
)
async def analyze_media_url(request: MediaAnalyzeRequest) -> MediaAnalyzeResponse:
    """Analyze a single media link from YouTube, TikTok, Instagram, Twitter, etc."""
    try:
        return await extractor_service.analyze_url(
            url=request.url,
            extract_flat=request.extract_flat,
        )
    except MediaExtractionError:
        raise
    except Exception as e:
        logger.error(f"Error in /analyze for URL {request.url}: {e}", exc_info=True)
        raise MediaExtractionError(f"Failed to analyze media: {str(e)}")


@router.post(
    "/batch-analyze",
    response_model=BatchAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch Analyze Multiple URLs",
    description="Concurrently analyze up to 50 media URLs or playlist entries with bounded concurrency.",
)
async def batch_analyze_urls(request: BatchAnalyzeRequest) -> BatchAnalyzeResponse:
    """Analyze multiple media URLs concurrently."""
    return await batch_service.analyze_batch(request)
