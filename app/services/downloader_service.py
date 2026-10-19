"""Async media downloader with WebSocket progress hooks, DASH stream merging, and audio transcoding."""

import asyncio
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
import yt_dlp  # type: ignore

try:
    from yt_dlp.networking.impersonate import ImpersonateTarget
except ImportError:
    ImpersonateTarget = None

from app.core.config import settings
from app.core.exceptions import DownloadTaskError, TaskNotFoundError
from app.core.logger import get_logger
from app.schemas.media_schemas import (
    DownloadRequest,
    DownloadTaskResponse,
    DownloadProgressEvent,
)
from app.services.ffmpeg_service import ffmpeg_service
from app.services.ws_manager import ws_manager
from app.utils.file_helpers import (
    sanitize_filename,
    format_bytes,
    format_speed,
    format_duration,
    parse_timestamp,
)

logger = get_logger(__name__)


@dataclass
class DownloadTaskState:
    """Internal state tracked for an active or completed download task."""
    task_id: str
    url: str
    status: str = "queued"
    progress_percent: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: Optional[str] = None
    eta: Optional[str] = None
    file_path: Optional[Path] = None
    filename: Optional[str] = None
    stream_url: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class DownloaderService:
    """Manages asynchronous media downloads with real-time WebSocket progress broadcasts."""

    def __init__(self) -> None:
        self.tasks: Dict[str, DownloadTaskState] = {}
        self._lock = asyncio.Lock()

    def get_task(self, task_id: str) -> Optional[DownloadTaskState]:
        """Fetch task state by task ID."""
        return self.tasks.get(task_id)

    def get_task_file(self, task_id: str) -> Path:
        """Resolve file path for a completed task or raise appropriate exception."""
        task = self.tasks.get(task_id)
        if not task:
            raise TaskNotFoundError(task_id)

        if task.status != "completed" or not task.file_path or not task.file_path.exists():
            raise DownloadTaskError(
                message=f"File for task '{task_id}' is not ready or has been removed.",
                details={"task_id": task_id, "status": task.status},
            )

        return task.file_path

    async def start_download(self, request: DownloadRequest) -> DownloadTaskResponse:
        """Initialize download job, create task record, and launch background worker."""
        task_id = str(uuid.uuid4())
        task_dir = settings.TEMP_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        task_state = DownloadTaskState(
            task_id=task_id,
            url=str(request.url),
            status="queued",
        )

        async with self._lock:
            self.tasks[task_id] = task_state

        # Initial progress event broadcast
        init_event = DownloadProgressEvent(
            task_id=task_id,
            status="queued",
            progress_percent=0.0,
            downloaded_bytes=0,
            total_bytes=0,
            downloaded_formatted="0 B",
            total_formatted="0 B",
        )
        ws_manager.broadcast_sync(task_id, init_event)

        # Launch background async worker
        asyncio.create_task(self._execute_download(task_id, task_dir, request))

        ws_url = f"/ws/progress/{task_id}"
        return DownloadTaskResponse(
            task_id=task_id,
            status="queued",
            message="Media download queued successfully.",
            ws_url=ws_url,
        )

    async def _execute_download(self, task_id: str, task_dir: Path, req: DownloadRequest) -> None:
        """Background coroutine coordinating extraction, download, and FFmpeg post-processing."""
        task = self.tasks.get(task_id)
        if not task:
            return

        try:
            task.status = "downloading"
            ws_manager.broadcast_sync(
                task_id,
                DownloadProgressEvent(
                    task_id=task_id,
                    status="downloading",
                    progress_percent=1.0,
                    downloaded_bytes=0,
                    total_bytes=0,
                    downloaded_formatted="0 B",
                    total_formatted="0 B",
                ),
            )

            # Download using yt-dlp in worker thread
            downloaded_file, meta = await asyncio.to_thread(
                self._run_ytdl_download, task_id, task_dir, req
            )

            # Post-Processing: Audio Extraction & Metadata Embedding
            task.status = "processing"
            ws_manager.broadcast_sync(
                task_id,
                DownloadProgressEvent(
                    task_id=task_id,
                    status="processing",
                    progress_percent=92.0,
                    downloaded_bytes=task.downloaded_bytes,
                    total_bytes=task.total_bytes,
                    downloaded_formatted=format_bytes(task.downloaded_bytes),
                    total_formatted=format_bytes(task.total_bytes),
                ),
            )

            final_file = downloaded_file

            # 1. Trimming if requested
            if req.start_time and req.end_time:
                start_sec = parse_timestamp(req.start_time)
                end_sec = parse_timestamp(req.end_time)
                trimmed_name = f"trimmed_{downloaded_file.stem}{downloaded_file.suffix}"
                trimmed_path = task_dir / trimmed_name
                final_file = await ffmpeg_service.trim_media(
                    input_path=downloaded_file,
                    output_path=trimmed_path,
                    start_time=start_sec,
                    end_time=end_sec,
                    extract_audio=req.extract_audio,
                    audio_format=req.audio_format,
                )

            # 2. Audio Transcoding if requested and not already trimmed as audio
            elif req.extract_audio:
                audio_name = f"{downloaded_file.stem}.{req.audio_format}"
                audio_path = task_dir / audio_name
                final_file = await ffmpeg_service.convert_to_audio(
                    input_path=downloaded_file,
                    output_path=audio_path,
                    audio_format=req.audio_format,
                    bitrate=f"{req.audio_quality}k",
                )

                # Embed ID3 Tags & Cover art
                if req.embed_metadata:
                    thumb_path = await self._download_thumbnail(meta.get("thumbnail"), task_dir)
                    await asyncio.to_thread(
                        ffmpeg_service.embed_id3_metadata,
                        audio_path=final_file,
                        title=meta.get("title"),
                        artist=meta.get("uploader") or meta.get("channel"),
                        album=meta.get("album") or "CBX Stream Downloads",
                        cover_art_path=thumb_path,
                    )

            # 3. Custom filename renaming if specified
            if req.custom_filename:
                safe_custom = sanitize_filename(req.custom_filename)
                custom_ext = final_file.suffix
                renamed_path = task_dir / f"{safe_custom}{custom_ext}"
                if renamed_path != final_file:
                    final_file = final_file.rename(renamed_path)

            # Download Complete
            task.status = "completed"
            task.file_path = final_file
            task.filename = final_file.name
            task.progress_percent = 100.0
            task.stream_url = f"{settings.API_V1_PREFIX}/stream/{task_id}"

            completed_event = DownloadProgressEvent(
                task_id=task_id,
                status="completed",
                progress_percent=100.0,
                downloaded_bytes=final_file.stat().st_size,
                total_bytes=final_file.stat().st_size,
                downloaded_formatted=format_bytes(final_file.stat().st_size),
                total_formatted=format_bytes(final_file.stat().st_size),
                filename=final_file.name,
                stream_url=task.stream_url,
            )
            ws_manager.broadcast_sync(task_id, completed_event)
            logger.info(f"Task {task_id} completed successfully: {final_file.name}")

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            task.status = "failed"
            task.error = str(e)
            error_event = DownloadProgressEvent(
                task_id=task_id,
                status="failed",
                progress_percent=0.0,
                error=str(e),
            )
            ws_manager.broadcast_sync(task_id, error_event)

    def _run_ytdl_download(
        self, task_id: str, task_dir: Path, req: DownloadRequest
    ) -> tuple[Path, Dict[str, Any]]:
        """Synchronous yt-dlp execution running within thread pool."""
        template_name = "%(title).100B.%(ext)s"
        outtmpl = str(task_dir / template_name)

        def progress_hook(d: Dict[str, Any]) -> None:
            if d.get("status") == "downloading":
                downloaded = int(d.get("downloaded_bytes", 0) or 0)
                raw_total = d.get("total_bytes") or d.get("total_bytes_estimate", 0) or 0
                total = int(raw_total)
                percent = (downloaded / total * 100.0) if total and total > 0 else 0.0
                speed = format_speed(d.get("speed"))
                eta = format_duration(d.get("eta"))

                task = self.tasks.get(task_id)
                if task:
                    task.downloaded_bytes = downloaded
                    task.total_bytes = total
                    task.progress_percent = min(90.0, max(1.0, percent * 0.9))
                    task.speed = speed
                    task.eta = eta

                event = DownloadProgressEvent(
                    task_id=task_id,
                    status="downloading",
                    progress_percent=round(task.progress_percent, 1) if task else 0.0,
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                    downloaded_formatted=format_bytes(downloaded),
                    total_formatted=format_bytes(total),
                    speed=speed,
                    eta=eta,
                )
                ws_manager.broadcast_sync(task_id, event)

        # Select format
        format_selector = req.format_id or "bestvideo+bestaudio/best"
        if req.extract_audio:
            format_selector = "bestaudio/best"

        ydl_opts: Dict[str, Any] = {
            "format": format_selector,
            "outtmpl": outtmpl,
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
            "ffmpeg_location": settings.FFMPEG_PATH,
            "geo_bypass": True,
            "socket_timeout": 30,
        }

        # Auto-configure JavaScript challenge solver runtime
        node_path = None
        if settings.NODE_PATH and os.path.exists(settings.NODE_PATH):
            node_path = settings.NODE_PATH
        elif shutil.which("node"):
            node_path = shutil.which("node")

        if node_path:
            ydl_opts["js_runtimes"] = {"node": {"path": node_path}}
        else:
            ydl_opts["js_runtimes"] = {"node": {}}

        # Configure browser TLS impersonation via curl_cffi
        if ImpersonateTarget is not None:
            try:
                ydl_opts["impersonate"] = ImpersonateTarget.from_str("chrome")
            except Exception:
                pass

        # Dynamically resolve cookies (supports hot-dropping cookies.txt without server restart)
        cookie_candidate = None
        if settings.COOKIES_FILE and os.path.exists(settings.COOKIES_FILE):
            cookie_candidate = settings.COOKIES_FILE
        elif (settings.BASE_DIR / "cookies.txt").exists():
            cookie_candidate = str(settings.BASE_DIR / "cookies.txt")
        elif (settings.TEMP_DIR / "cookies.txt").exists():
            cookie_candidate = str(settings.TEMP_DIR / "cookies.txt")

        if cookie_candidate:
            ydl_opts["cookiefile"] = cookie_candidate
        elif settings.COOKIES_FROM_BROWSER:
            ydl_opts["cookiesfrombrowser"] = (settings.COOKIES_FROM_BROWSER,)

        if settings.PROXY_URL:
            ydl_opts["proxy"] = settings.PROXY_URL

        def _execute(opts_dict: Dict[str, Any]) -> tuple[Path, Dict[str, Any]]:
            with yt_dlp.YoutubeDL(opts_dict) as ydl:
                meta = ydl.extract_info(str(req.url), download=True)
                if not meta:
                    raise DownloadTaskError("Failed to extract media information during download.")

                # Identify downloaded file
                downloaded_files = [
                    f for f in task_dir.iterdir()
                    if f.is_file() and not f.name.endswith(".part") and not f.name.endswith(".ytdl")
                ]
                if not downloaded_files:
                    raise DownloadTaskError("No output file generated by media extractor.")

                # Grab newest file
                downloaded_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                return downloaded_files[0], meta

        try:
            return _execute(ydl_opts)
        except Exception as e_first:
            # If download failed with cookies, retry without cookies
            if "cookiefile" in ydl_opts or "cookiesfrombrowser" in ydl_opts:
                logger.info(f"Retrying download for {req.url} without cookies (clean guest session)...")
                retry_opts = dict(ydl_opts)
                retry_opts.pop("cookiefile", None)
                retry_opts.pop("cookiesfrombrowser", None)
                try:
                    return _execute(retry_opts)
                except Exception as e_retry:
                    logger.warning(f"Download retry without cookies also failed: {e_retry}")
            raise e_first

    async def _download_thumbnail(self, thumb_url: Optional[str], task_dir: Path) -> Optional[Path]:
        """Download remote cover art for embedding into ID3 tags."""
        if not thumb_url:
            return None

        try:
            thumb_path = task_dir / "cover.jpg"
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(thumb_url)
                if resp.status_code == 200:
                    thumb_path.write_bytes(resp.content)
                    return thumb_path
        except Exception as e:
            logger.warning(f"Could not download thumbnail for cover embedding: {e}")

        return None


# Singleton downloader service instance
downloader_service = DownloaderService()
