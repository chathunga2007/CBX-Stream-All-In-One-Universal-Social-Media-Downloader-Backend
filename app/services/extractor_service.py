"""Deep media metadata and format analyzer combining yt-dlp and gallery-dl."""

import asyncio
import json
import os
import shutil
import subprocess
from typing import Dict, Any, List, Optional
import yt_dlp  # type: ignore

from app.core.config import settings
from app.core.exceptions import MediaExtractionError
from app.core.logger import get_logger
from app.schemas.media_schemas import (
    MediaAnalyzeResponse,
    PlatformTheme,
    MediaFormat,
    CarouselMediaItem,
)
from app.utils.file_helpers import format_duration
from app.utils.format_parser import parse_media_formats
from app.utils.platform_detector import detect_platform

logger = get_logger(__name__)

# Standard modern User-Agent for web requests
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class ExtractorService:
    """Extracts deep metadata, stream formats, and gallery slides across 1000+ platforms."""

    def _get_ytdl_base_opts(self, extract_flat: bool = False) -> Dict[str, Any]:
        """Construct standard production yt-dlp extraction options."""
        opts: Dict[str, Any] = {
            "extract_flat": extract_flat,
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "ignoreerrors": False,
            "geo_bypass": True,
            "socket_timeout": 20,
            "user_agent": DEFAULT_USER_AGENT,
        }

        # Auto-configure JavaScript challenge solver runtime
        if settings.NODE_PATH and os.path.exists(settings.NODE_PATH):
            opts["js_runtimes"] = {"node": {"path": settings.NODE_PATH}}
        elif shutil.which("node"):
            opts["js_runtimes"] = {"node": {"path": shutil.which("node")}}

        # Dynamically resolve cookies (supports hot-dropping cookies.txt without server restart)
        cookie_candidate = None
        if settings.COOKIES_FILE and os.path.exists(settings.COOKIES_FILE):
            cookie_candidate = settings.COOKIES_FILE
        elif (settings.BASE_DIR / "cookies.txt").exists():
            cookie_candidate = str(settings.BASE_DIR / "cookies.txt")
        elif (settings.TEMP_DIR / "cookies.txt").exists():
            cookie_candidate = str(settings.TEMP_DIR / "cookies.txt")

        if cookie_candidate:
            opts["cookiefile"] = cookie_candidate
        elif settings.COOKIES_FROM_BROWSER:
            opts["cookiesfrombrowser"] = (settings.COOKIES_FROM_BROWSER,)

        if settings.PROXY_URL:
            opts["proxy"] = settings.PROXY_URL

        return opts

    def _extract_via_ytdl_sync(self, url: str, extract_flat: bool = False) -> Dict[str, Any]:
        """Synchronously extract metadata via yt-dlp (runs in background thread)."""
        opts = self._get_ytdl_base_opts(extract_flat)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise MediaExtractionError(f"No media metadata could be extracted from: {url}")
                return ydl.sanitize_info(info)
        except yt_dlp.utils.DownloadError as e:
            error_text = str(e)
            logger.warning(f"yt-dlp extraction failed for {url}: {error_text}")

            # Provide clean, actionable instructions if YouTube triggers bot detection
            if "Sign in to confirm you’re not a bot" in error_text or "confirm you're not a bot" in error_text:
                friendly_msg = (
                    "YouTube requested bot verification for this video. "
                    "To enable restricted video downloads, please export YouTube cookies into a "
                    "'cookies.txt' file (using 'Get cookies.txt LOCALLY' Chrome/Firefox extension) "
                    "and place it in the project root folder."
                )
                raise MediaExtractionError(
                    message=friendly_msg,
                    details={"url": url, "error": error_text, "requires_cookies": True},
                )

            raise MediaExtractionError(
                message=f"Failed to extract media: {error_text}",
                details={"url": url, "error": error_text},
            )
        except Exception as e:
            logger.error(f"Unexpected error extracting {url}: {e}", exc_info=True)
            raise MediaExtractionError(
                message=f"Extraction error: {str(e)}",
                details={"url": url, "error": str(e)},
            )

    def _extract_via_gallery_dl_sync(self, url: str) -> List[Dict[str, Any]]:
        """Fallback gallery extractor for multi-image albums (Instagram carousels, Pinterest, etc.)."""
        gallery_items: List[Dict[str, Any]] = []
        try:
            # Check gallery-dl via CLI or library
            cmd = ["gallery-dl", "--dump-json", "--no-download", url]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            if proc.returncode == 0 and proc.stdout:
                for line in proc.stdout.strip().split("\n"):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if isinstance(data, list) and len(data) >= 2:
                            # gallery-dl often returns [type_id, dict_data]
                            item_dict = data[1] if isinstance(data[1], dict) else {}
                            direct_url = data[2] if len(data) > 2 and isinstance(data[2], str) else item_dict.get("url")
                            if direct_url:
                                gallery_items.append({"url": direct_url, **item_dict})
                        elif isinstance(data, dict):
                            gallery_items.append(data)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.debug(f"gallery-dl probing fallback caught non-fatal exception: {e}")

        return gallery_items

    async def analyze_url(self, url: str, extract_flat: bool = False) -> MediaAnalyzeResponse:
        """Analyze a media URL asynchronously and return complete metadata with Chameleon theme."""
        # Detect platform and generate Chameleon Glass UI theme tokens
        theme_info = detect_platform(url)
        platform_theme = PlatformTheme(**theme_info.to_dict())

        # Offload yt-dlp extraction to thread
        info = await asyncio.to_thread(self._extract_via_ytdl_sync, url, extract_flat)

        # Handle playlist or multiple entries
        entries = info.get("entries")
        first_entry = None
        carousel_items: List[CarouselMediaItem] = []
        is_carousel = False

        if entries and isinstance(entries, list):
            # Could be a multi-photo carousel or playlist
            valid_entries = [e for e in entries if e]
            if len(valid_entries) > 1:
                is_carousel = True
                for idx, entry in enumerate(valid_entries, start=1):
                    # Check if entry is image or video
                    media_url = entry.get("url") or entry.get("webpage_url")
                    if not media_url and entry.get("formats"):
                        media_url = entry["formats"][-1].get("url")

                    thumb = entry.get("thumbnail") or (entry.get("thumbnails")[-1].get("url") if entry.get("thumbnails") else None)
                    vcodec = entry.get("vcodec", "none")
                    m_type = "video" if vcodec != "none" or entry.get("duration") else "image"

                    if media_url:
                        carousel_items.append(
                            CarouselMediaItem(
                                index=idx,
                                url=media_url,
                                thumbnail=thumb or media_url,
                                media_type=m_type,
                                width=entry.get("width"),
                                height=entry.get("height"),
                                caption=entry.get("title") or entry.get("description"),
                            )
                        )
                first_entry = valid_entries[0]
            elif len(valid_entries) == 1:
                first_entry = valid_entries[0]

        target_info = first_entry if first_entry else info

        # Parse formats and categorize into 4K/2K/1080p/Audio tiers
        raw_formats = target_info.get("formats", []) or []
        duration = target_info.get("duration")
        formats_collection = parse_media_formats(raw_formats, duration=duration)

        # If it's Instagram, TikTok, or Pinterest and yt-dlp found no video formats, check gallery-dl
        if not formats_collection.video_formats and not is_carousel and theme_info.id in ["instagram", "pinterest", "tiktok", "reddit"]:
            gallery_data = await asyncio.to_thread(self._extract_via_gallery_dl_sync, url)
            if gallery_data:
                is_carousel = True
                for idx, item in enumerate(gallery_data, start=1):
                    direct_url = item.get("url") or item.get("source_url")
                    if direct_url:
                        carousel_items.append(
                            CarouselMediaItem(
                                index=idx,
                                url=direct_url,
                                thumbnail=item.get("thumbnail") or direct_url,
                                media_type="image",
                                width=item.get("width"),
                                height=item.get("height"),
                                caption=item.get("description") or item.get("title"),
                            )
                        )

        # Build schema models
        all_formats = [MediaFormat(**fmt.to_dict()) for fmt in formats_collection.all_formats]
        video_formats = [MediaFormat(**fmt.to_dict()) for fmt in formats_collection.video_formats]
        audio_formats = [MediaFormat(**fmt.to_dict()) for fmt in formats_collection.audio_formats]

        # Extract primary metadata fields
        title = (
            target_info.get("title")
            or target_info.get("description")
            or f"{platform_theme.name} Media"
        )
        # Clean title of newlines for cleaner header display
        title = title.split("\n")[0].strip()[:150]

        thumbnail_url = target_info.get("thumbnail")
        if not thumbnail_url and target_info.get("thumbnails"):
            thumbnail_url = target_info["thumbnails"][-1].get("url")

        return MediaAnalyzeResponse(
            url=url,
            title=title,
            description=target_info.get("description"),
            uploader=target_info.get("uploader") or target_info.get("channel"),
            uploader_id=target_info.get("uploader_id") or target_info.get("channel_id"),
            uploader_url=target_info.get("uploader_url") or target_info.get("channel_url"),
            duration=duration,
            duration_formatted=format_duration(duration),
            thumbnail=thumbnail_url,
            is_live=bool(target_info.get("is_live")),
            view_count=target_info.get("view_count"),
            like_count=target_info.get("like_count"),
            upload_date=str(target_info.get("upload_date") or ""),
            platform=platform_theme,
            formats=all_formats,
            video_formats=video_formats,
            audio_formats=audio_formats,
            is_carousel=is_carousel,
            carousel_items=carousel_items,
        )


# Singleton extractor instance
extractor_service = ExtractorService()
