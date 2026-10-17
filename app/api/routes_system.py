"""System health check, diagnostics, and environment status endpoint."""

import shutil
import sys
import time
from fastapi import APIRouter, status, UploadFile, File, HTTPException

from app.core.config import settings
from app.schemas.media_schemas import HealthResponse
from app.services.downloader_service import downloader_service
from app.services.ffmpeg_service import ffmpeg_service

router = APIRouter(tags=["System Health & Diagnostics"])

START_TIME = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health & Diagnostics",
    description="Check backend server health, FFmpeg availability, active download tasks, and disk capacity.",
)
async def system_health_check() -> HealthResponse:
    """Return comprehensive system health and hardware diagnostics."""
    uptime = time.time() - START_TIME
    active_tasks_count = sum(
        1 for t in downloader_service.tasks.values() if t.status in ["queued", "downloading", "processing"]
    )

    # Disk usage in temp directory drive
    total, used, free = shutil.disk_usage(str(settings.TEMP_DIR))
    disk_free_gb = round(free / (1024 ** 3), 2)
    disk_total_gb = round(total / (1024 ** 3), 2)

    ffmpeg_ok = await ffmpeg_service.check_ffmpeg_available()

    return HealthResponse(
        status="healthy" if ffmpeg_ok else "degraded",
        version=settings.VERSION,
        uptime_seconds=round(uptime, 2),
        active_tasks=active_tasks_count,
        disk_free_gb=disk_free_gb,
        disk_total_gb=disk_total_gb,
        ffmpeg_available=ffmpeg_ok,
        ffmpeg_path=settings.FFMPEG_PATH,
        python_version=sys.version.split(" ")[0],
    )


@router.post(
    "/cookies",
    status_code=status.HTTP_200_OK,
    summary="Upload or Update YouTube Cookies",
    description="Upload a cookies.txt file to bypass YouTube bot detection and access age/sign-in restricted videos.",
)
async def upload_cookies_file(
    file: UploadFile = File(..., description="Netscape formatted cookies.txt file from browser")
) -> dict:
    """Store exported browser cookies directly into the project root."""
    content = await file.read()
    if not content or len(content.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded cookies file is empty or invalid.",
        )

    target_path = settings.BASE_DIR / "cookies.txt"
    target_path.write_bytes(content)
    settings.COOKIES_FILE = str(target_path)

    return {
        "success": True,
        "message": "Cookies successfully saved to cookies.txt! YouTube bot verification is now bypassed.",
        "file_size_bytes": len(content),
    }


@router.get(
    "/cookies",
    status_code=status.HTTP_200_OK,
    summary="Check YouTube Cookies Status",
    description="Check whether cookies.txt is currently loaded to bypass YouTube bot detection.",
)
async def check_cookies_status() -> dict:
    """Check active cookies status."""
    import os
    cookie_path = (
        settings.COOKIES_FILE
        if (settings.COOKIES_FILE and os.path.exists(settings.COOKIES_FILE))
        else (
            str(settings.BASE_DIR / "cookies.txt")
            if (settings.BASE_DIR / "cookies.txt").exists()
            else None
        )
    )
    return {
        "configured": cookie_path is not None,
        "cookies_path": cookie_path,
        "instructions": (
            "Export YouTube cookies using 'Get cookies.txt LOCALLY' extension, and upload "
            "via POST /api/v1/cookies or place as 'cookies.txt' in project root."
        ),
    }
