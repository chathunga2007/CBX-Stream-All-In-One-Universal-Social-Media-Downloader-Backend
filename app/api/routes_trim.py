"""Endpoints for media timestamp precision trimming and clipping."""

import asyncio
import uuid
from pathlib import Path
from fastapi import APIRouter, status

from app.core.config import settings
from app.core.exceptions import InvalidTimestampError, TaskNotFoundError, FFmpegProcessError
from app.core.logger import get_logger
from app.schemas.media_schemas import (
    TrimRequest,
    TrimResponse,
    DownloadRequest,
    ErrorResponse,
)
from app.services.downloader_service import downloader_service, DownloadTaskState
from app.services.ffmpeg_service import ffmpeg_service
from app.utils.file_helpers import (
    parse_timestamp,
    format_duration,
    sanitize_filename,
)

logger = get_logger(__name__)

router = APIRouter(tags=["Media Trimming & Clipping"])


@router.post(
    "/trim",
    response_model=TrimResponse,
    status_code=status.HTTP_200_OK,
    summary="Precision Timestamp Trimmer",
    description="Trim a video or audio clip between start_time and end_time from an existing task or direct URL.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid timestamps or input"},
        404: {"model": ErrorResponse, "description": "Source task not found"},
        500: {"model": ErrorResponse, "description": "Trimming process failed"},
    },
)
async def trim_media_clip(request: TrimRequest) -> TrimResponse:
    """Trim a specific time window from a video or audio stream."""
    start_sec = parse_timestamp(request.start_time)
    end_sec = parse_timestamp(request.end_time)

    if end_sec <= start_sec:
        raise InvalidTimestampError(
            f"End time ({request.end_time}) must be greater than start time ({request.start_time})."
        )

    duration = end_sec - start_sec
    new_task_id = str(uuid.uuid4())
    task_dir = settings.TEMP_DIR / new_task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    source_file: Path

    # Case A: Trimming an already downloaded task
    if request.task_id:
        source_file = downloader_service.get_task_file(request.task_id)

    # Case B: Direct URL provided - download source first
    elif request.url:
        dl_req = DownloadRequest(
            url=request.url,
            format_id=request.format_id or "bestvideo+bestaudio/best",
            extract_audio=request.extract_audio,
            audio_format=request.audio_format,
        )
        task_res = await downloader_service.start_download(dl_req)
        # Wait for download completion
        for _ in range(60):
            await asyncio.sleep(1.0)
            t = downloader_service.get_task(task_res.task_id)
            if t and t.status == "completed" and t.file_path:
                source_file = t.file_path
                break
            elif t and t.status == "failed":
                raise FFmpegProcessError(f"Pre-download failed for URL trim: {t.error}")
        else:
            raise FFmpegProcessError("Download timed out while preparing media for trim.")
    else:
        raise InvalidTimestampError("Must provide either 'task_id' or 'url' to trim.")

    # Determine output extension and filename
    ext = f".{request.audio_format}" if request.extract_audio else source_file.suffix
    base_name = request.custom_filename or f"clip_{int(start_sec)}s_to_{int(end_sec)}s_{source_file.stem}"
    clean_filename = f"{sanitize_filename(base_name)}{ext}"
    output_path = task_dir / clean_filename

    # Execute FFmpeg trim
    trimmed_path = await ffmpeg_service.trim_media(
        input_path=source_file,
        output_path=output_path,
        start_time=start_sec,
        end_time=end_sec,
        extract_audio=request.extract_audio,
        audio_format=request.audio_format,
    )

    # Register completed task for streaming
    stream_url = f"{settings.API_V1_PREFIX}/stream/{new_task_id}"
    task_state = DownloadTaskState(
        task_id=new_task_id,
        url=f"trim://{source_file.name}",
        status="completed",
        progress_percent=100.0,
        file_path=trimmed_path,
        filename=trimmed_path.name,
        stream_url=stream_url,
    )
    downloader_service.tasks[new_task_id] = task_state

    logger.info(f"Trim completed for task {new_task_id}: {trimmed_path.name} ({duration:.2f}s)")

    return TrimResponse(
        task_id=new_task_id,
        status="completed",
        filename=trimmed_path.name,
        stream_url=stream_url,
        duration=duration,
        duration_formatted=format_duration(duration),
    )
