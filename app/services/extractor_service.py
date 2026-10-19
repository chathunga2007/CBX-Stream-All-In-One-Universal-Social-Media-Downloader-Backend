"""Deep media metadata and format analyzer combining yt-dlp, curl-cffi, and gallery-dl."""

import asyncio
import json
import os
import shutil
import subprocess
from typing import Dict, Any, List, Optional
import yt_dlp  # type: ignore

try:
    from yt_dlp.networking.impersonate import ImpersonateTarget
except ImportError:
    ImpersonateTarget = None

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

    def _get_ytdl_base_opts(
        self,
        extract_flat: bool = False,
        use_cookies: bool = True,
        player_clients: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Construct resilient yt-dlp extraction options with Node challenge solver & browser impersonation."""
        opts: Dict[str, Any] = {
            "extract_flat": extract_flat,
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "ignoreerrors": False,
            "geo_bypass": True,
            "socket_timeout": 25,
            "user_agent": DEFAULT_USER_AGENT,
            "noplaylist": not extract_flat,
        }

        # Auto-configure JavaScript challenge solver runtime for modern YouTube botguard/EJS
        node_path = None
        if settings.NODE_PATH and os.path.exists(settings.NODE_PATH):
            node_path = settings.NODE_PATH
        elif shutil.which("node"):
            node_path = shutil.which("node")

        if node_path:
            opts["js_runtimes"] = {"node": {"path": node_path}}
        else:
            opts["js_runtimes"] = {"node": {}}

        # Configure browser TLS impersonation via curl_cffi for Cloudflare / TikTok / Instagram bypass
        if ImpersonateTarget is not None:
            try:
                opts["impersonate"] = ImpersonateTarget.from_str("chrome")
            except Exception:
                pass

        # Player client rotation if explicitly specified
        if player_clients:
            opts["extractor_args"] = {"youtube": {"player_client": player_clients}}

        # Dynamically resolve cookies (supports hot-dropping cookies.txt without server restart)
        if use_cookies:
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
        """Synchronously extract metadata via yt-dlp with automatic multi-tier anti-bot fallback."""
        # 1. Primary Attempt: Use default configuration (including cookies if present)
        opts = self._get_ytdl_base_opts(extract_flat=extract_flat, use_cookies=True)
        used_cookies = "cookiefile" in opts or "cookiesfrombrowser" in opts

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    return ydl.sanitize_info(info)
        except Exception as e_first:
            first_err_str = str(e_first)
            logger.warning(f"Primary yt-dlp extraction failed for {url}: {first_err_str}")

            # 2. Secondary Attempt: If cookies failed or caused 'Sign in to confirm you’re not a bot', retry WITHOUT cookies
            if used_cookies:
                logger.info(f"Retrying extraction for {url} without cookies (clean guest session)...")
                opts_nocookies = self._get_ytdl_base_opts(extract_flat=extract_flat, use_cookies=False)
                try:
                    with yt_dlp.YoutubeDL(opts_nocookies) as ydl:
                        info = ydl.extract_info(url, download=False)
                        if info:
                            return ydl.sanitize_info(info)
                except Exception as e_second:
                    logger.warning(f"Secondary (no-cookies) extraction also failed for {url}: {e_second}")

            # 3. Tertiary Attempt (YouTube only): Client rotation (iOS / Android / mweb clients)
            if "youtube.com" in url or "youtu.be" in url:
                logger.info(f"Retrying YouTube extraction for {url} with client rotation [ios, android, mweb]...")
                opts_clients = self._get_ytdl_base_opts(
                    extract_flat=extract_flat,
                    use_cookies=False,
                    player_clients=["ios", "android", "mweb", "web"],
                )
                try:
                    with yt_dlp.YoutubeDL(opts_clients) as ydl:
                        info = ydl.extract_info(url, download=False)
                        if info:
                            return ydl.sanitize_info(info)
                except Exception as e_third:
                    logger.warning(f"Tertiary client rotation failed for {url}: {e_third}")

            # Pick the most accurate error message across attempts (e.g. video unavailable vs anti-bot)
            all_errors = [str(e) for e in [e_first, locals().get("e_second"), locals().get("e_third")] if e]
            specific_err = next((e for e in all_errors if "unavailable" in e.lower() or "private" in e.lower() or "deleted" in e.lower()), None)
            final_err_str = specific_err or first_err_str

            if "This video is unavailable" in final_err_str or "video is unavailable" in final_err_str.lower():
                raise MediaExtractionError(
                    message="This video is unavailable, deleted, or removed on YouTube.",
                    details={"url": url, "error": final_err_str},
                )

            # If it's YouTube bot verification, provide helpful instructions
            if "Sign in to confirm you’re not a bot" in final_err_str or "confirm you're not a bot" in final_err_str:
                friendly_msg = (
                    "YouTube requested bot verification for this video. "
                    "To enable restricted video downloads, please export YouTube cookies into a "
                    "'cookies.txt' file (using 'Get cookies.txt LOCALLY' Chrome/Firefox extension) "
                    "and place it in the project root folder."
                )
                raise MediaExtractionError(
                    message=friendly_msg,
                    details={"url": url, "error": final_err_str, "requires_cookies": True},
                )

            raise MediaExtractionError(
                message=f"Failed to extract media: {final_err_str}",
                details={"url": url, "error": final_err_str},
            )

    def _extract_via_gallery_dl_sync(self, url: str) -> List[Dict[str, Any]]:
        """Fallback gallery extractor for multi-image albums (Instagram carousels, Pinterest, etc.)."""
        gallery_items: List[Dict[str, Any]] = []
        try:
            cmd = ["gallery-dl", "--dump-json", "--no-download", url]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            if proc.returncode == 0 and proc.stdout:
                for line in proc.stdout.strip().split("\n"):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if isinstance(data, list) and len(data) >= 2:
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

        info: Optional[Dict[str, Any]] = None
        ytdl_error: Optional[Exception] = None

        # 1. Attempt deep extraction via yt-dlp
        try:
            info = await asyncio.to_thread(self._extract_via_ytdl_sync, url, extract_flat)
        except Exception as e:
            ytdl_error = e
            logger.info(f"yt-dlp could not extract {url}. Checking gallery-dl fallback...")

        # 2. If yt-dlp failed or returned no items, check gallery-dl for Instagram / Pinterest / Reddit / Twitter
        if (not info or not info.get("formats")) and theme_info.id in ["instagram", "pinterest", "tiktok", "reddit", "twitter"]:
            gallery_data = await asyncio.to_thread(self._extract_via_gallery_dl_sync, url)
            if gallery_data:
                logger.info(f"gallery-dl successfully recovered {len(gallery_data)} items for {url}!")
                carousel_items: List[CarouselMediaItem] = []
                for idx, item in enumerate(gallery_data, start=1):
                    direct_url = item.get("url") or item.get("source_url")
                    if direct_url:
                        carousel_items.append(
                            CarouselMediaItem(
                                index=idx,
                                url=direct_url,
                                thumbnail=item.get("thumbnail") or direct_url,
                                media_type="video" if str(direct_url).endswith(".mp4") else "image",
                                width=item.get("width"),
                                height=item.get("height"),
                                caption=item.get("description") or item.get("title") or f"Item {idx}",
                            )
                        )

                if carousel_items:
                    primary_thumb = carousel_items[0].thumbnail or carousel_items[0].url
                    title = carousel_items[0].caption or f"{platform_theme.name} Post"
                    return MediaAnalyzeResponse(
                        url=url,
                        title=title[:150],
                        description=f"Extracted {len(carousel_items)} items via Gallery Extractor",
                        uploader=gallery_data[0].get("author") or gallery_data[0].get("user") or platform_theme.name,
                        thumbnail=primary_thumb,
                        platform=platform_theme,
                        formats=[],
                        video_formats=[],
                        audio_formats=[],
                        is_carousel=True,
                        carousel_items=carousel_items,
                    )

        # If yt-dlp had an error and gallery-dl couldn't recover, raise the original error
        if info is None:
            if ytdl_error:
                raise ytdl_error
            raise MediaExtractionError(f"No media found for URL: {url}")

        # Handle playlist or multiple entries
        entries = info.get("entries")
        first_entry = None
        carousel_items: List[CarouselMediaItem] = []
        is_carousel = False

        if entries and isinstance(entries, list):
            valid_entries = [e for e in entries if e]
            if len(valid_entries) > 1:
                is_carousel = True
                for idx, entry in enumerate(valid_entries, start=1):
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

        # If yt-dlp found no video formats, check gallery-dl as supplemental
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
