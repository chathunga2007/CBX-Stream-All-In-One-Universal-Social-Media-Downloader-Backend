"""Multi-photo and video gallery extractor, async ZIP bundler, and CORS proxy streamer."""

import asyncio
import io
import mimetypes
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional, AsyncIterator, Tuple, Dict, Any

import httpx
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.exceptions import CarouselExtractionError
from app.core.logger import get_logger
from app.schemas.media_schemas import (
    CarouselZipResponse,
    DownloadProgressEvent,
)
from app.services.downloader_service import downloader_service, DownloadTaskState
from app.services.ws_manager import ws_manager
from app.utils.file_helpers import sanitize_filename, format_bytes

logger = get_logger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}


class CarouselService:
    """Handles multi-media downloading, ZIP archive compression, and proxy streaming."""

    async def bundle_carousel_zip(
        self,
        media_urls: List[str],
        custom_filename: Optional[str] = None,
    ) -> CarouselZipResponse:
        """Download all carousel items concurrently and package them into a single ZIP archive."""
        if not media_urls:
            raise CarouselExtractionError("No media URLs provided for ZIP bundling.")

        task_id = str(uuid.uuid4())
        task_dir = settings.TEMP_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        task_state = DownloadTaskState(
            task_id=task_id,
            url="carousel_bundle",
            status="downloading",
        )
        downloader_service.tasks[task_id] = task_state

        # Initial progress broadcast
        ws_manager.broadcast_sync(
            task_id,
            DownloadProgressEvent(
                task_id=task_id,
                status="downloading",
                progress_percent=5.0,
                downloaded_bytes=0,
                total_bytes=0,
                downloaded_formatted="0 B",
                total_formatted="0 B",
            ),
        )

        downloaded_files: List[Path] = []
        total_items = len(media_urls)

        # Download each item
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True, headers=DEFAULT_HEADERS) as client:
            for idx, item_url in enumerate(media_urls, start=1):
                try:
                    resp = await client.get(item_url)
                    if resp.status_code == 200:
                        # Determine file extension from content-type or URL
                        content_type = resp.headers.get("content-type", "")
                        ext = mimetypes.guess_extension(content_type) or ".jpg"
                        if ext == ".jpe":
                            ext = ".jpg"
                        if "video" in content_type:
                            ext = ".mp4"

                        item_name = f"slide_{idx:02d}{ext}"
                        item_path = task_dir / item_name
                        item_path.write_bytes(resp.content)
                        downloaded_files.append(item_path)

                        # Update progress percentage
                        pct = round((idx / total_items) * 80.0, 1)
                        ws_manager.broadcast_sync(
                            task_id,
                            DownloadProgressEvent(
                                task_id=task_id,
                                status="downloading",
                                progress_percent=pct,
                                downloaded_bytes=len(resp.content),
                                total_bytes=0,
                                downloaded_formatted=format_bytes(len(resp.content)),
                                total_formatted="--",
                            ),
                        )
                except Exception as e:
                    logger.warning(f"Failed to fetch carousel item {idx} ({item_url}): {e}")

        if not downloaded_files:
            raise CarouselExtractionError("Failed to download any media items for this carousel.")

        # ZIP packaging phase
        task_state.status = "processing"
        ws_manager.broadcast_sync(
            task_id,
            DownloadProgressEvent(
                task_id=task_id,
                status="processing",
                progress_percent=85.0,
                downloaded_bytes=0,
                total_bytes=0,
                downloaded_formatted="--",
                total_formatted="--",
            ),
        )

        base_zip_name = sanitize_filename(custom_filename or f"carousel_album_{task_id[:8]}")
        zip_path = task_dir / f"{base_zip_name}.zip"

        def _make_zip() -> None:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in downloaded_files:
                    zip_file.write(file_path, arcname=file_path.name)

        await asyncio.to_thread(_make_zip)

        total_size = zip_path.stat().st_size
        stream_url = f"{settings.API_V1_PREFIX}/stream/{task_id}"

        # Register completed state
        task_state.status = "completed"
        task_state.file_path = zip_path
        task_state.filename = zip_path.name
        task_state.stream_url = stream_url
        task_state.progress_percent = 100.0

        completed_event = DownloadProgressEvent(
            task_id=task_id,
            status="completed",
            progress_percent=100.0,
            downloaded_bytes=total_size,
            total_bytes=total_size,
            downloaded_formatted=format_bytes(total_size),
            total_formatted=format_bytes(total_size),
            filename=zip_path.name,
            stream_url=stream_url,
        )
        ws_manager.broadcast_sync(task_id, completed_event)

        logger.info(f"Carousel ZIP created successfully for task {task_id}: {zip_path.name} ({len(downloaded_files)} items)")

        return CarouselZipResponse(
            task_id=task_id,
            zip_url=stream_url,
            file_count=len(downloaded_files),
            total_size_bytes=total_size,
            total_size_formatted=format_bytes(total_size),
        )

    async def proxy_media_stream(self, url: str) -> StreamingResponse:
        """Stream remote media through backend to bypass CORS and CDN referer checks."""
        headers = {
            "User-Agent": DEFAULT_HEADERS["User-Agent"],
            "Accept": "*/*",
        }

        client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        req = client.build_request("GET", url, headers=headers)
        resp = await client.send(req, stream=True)

        if resp.status_code >= 400:
            await resp.aclose()
            await client.aclose()
            raise CarouselExtractionError(
                f"Failed to fetch proxy media from upstream server. HTTP {resp.status_code}"
            )

        content_type = resp.headers.get("content-type", "application/octet-stream")

        async def stream_generator() -> AsyncIterator[bytes]:
            try:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    yield chunk
            finally:
                await resp.aclose()
                await client.aclose()

        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=86400",
        }
        if "content-length" in resp.headers:
            response_headers["Content-Length"] = resp.headers["content-length"]

        return StreamingResponse(
            stream_generator(),
            media_type=content_type,
            headers=response_headers,
        )


# Singleton carousel service
carousel_service = CarouselService()
