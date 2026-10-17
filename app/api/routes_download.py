"""Endpoints for initiating downloads, checking status, and streaming completed media files."""

import mimetypes
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse

from app.core.exceptions import TaskNotFoundError, DownloadTaskError
from app.core.logger import get_logger
from app.schemas.media_schemas import (
    DownloadRequest,
    DownloadTaskResponse,
    DownloadProgressEvent,
    ErrorResponse,
)
from app.services.downloader_service import downloader_service
from app.utils.file_helpers import format_bytes

logger = get_logger(__name__)

router = APIRouter(tags=["Media Download & Streaming"])


@router.post(
    "/download",
    response_model=DownloadTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Media Download Task",
    description="Queue an async media download with options for DASH merge, audio extraction, and trimming.",
    responses={
        500: {"model": ErrorResponse, "description": "Download failed to initiate"},
    },
)
async def create_download_task(request: DownloadRequest) -> DownloadTaskResponse:
    """Initiate an async download job for the given media URL."""
    return await downloader_service.start_download(request)


@router.get(
    "/download/status/{task_id}",
    response_model=DownloadProgressEvent,
    status_code=status.HTTP_200_OK,
    summary="Get Download Task Status",
    description="Check the current progress, status, speed, and metadata of an active or completed task.",
    responses={
        404: {"model": ErrorResponse, "description": "Task ID not found"},
    },
)
async def get_download_status(task_id: str) -> DownloadProgressEvent:
    """Retrieve the current progress and status for a given task ID."""
    task = downloader_service.get_task(task_id)
    if not task:
        raise TaskNotFoundError(task_id)

    return DownloadProgressEvent(
        task_id=task.task_id,
        status=task.status,
        progress_percent=task.progress_percent,
        downloaded_bytes=task.downloaded_bytes,
        total_bytes=task.total_bytes,
        downloaded_formatted=format_bytes(task.downloaded_bytes),
        total_formatted=format_bytes(task.total_bytes),
        speed=task.speed,
        eta=task.eta,
        filename=task.filename,
        stream_url=task.stream_url,
        error=task.error,
    )


@router.get(
    "/stream/{task_id}",
    summary="Stream or Download Media File",
    description="Stream the completed audio/video file with byte-range support or trigger file download.",
    responses={
        404: {"model": ErrorResponse, "description": "File not found or task incomplete"},
        200: {"description": "Media file streamed successfully"},
    },
)
async def stream_media_file(
    task_id: str,
    inline: bool = Query(
        default=False,
        description="If True, serve inline for in-browser playback; if False, trigger download attachment",
    ),
):
    """Serve completed media file with proper MIME type and Content-Disposition headers."""
    file_path = downloader_service.get_task_file(task_id)
    task = downloader_service.get_task(task_id)

    mime_type, _ = mimetypes.guess_type(file_path.name)
    if not mime_type:
        mime_type = "application/octet-stream"

    filename = (task.filename if task and task.filename else file_path.name)
    disposition = "inline" if inline else "attachment"

    return FileResponse(
        path=str(file_path),
        media_type=mime_type,
        filename=filename,
        content_disposition_type=disposition,
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        },
    )
