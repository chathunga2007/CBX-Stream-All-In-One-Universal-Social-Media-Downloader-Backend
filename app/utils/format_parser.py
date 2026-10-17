"""Cleans, categorizes, and groups raw yt-dlp format streams into 4K/2K/1080p/720p and HQ Audio."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from app.utils.file_helpers import format_bytes


@dataclass
class ParsedFormat:
    """Standardized representation of an extractable media format."""
    format_id: str
    ext: str
    resolution: str
    quality_label: str
    height: Optional[int]
    fps: Optional[int]
    filesize: Optional[int]
    filesize_formatted: str
    vcodec: str
    acodec: str
    is_video_only: bool
    is_audio_only: bool
    has_video_and_audio: bool
    tbr: Optional[float]
    url: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FormatsCollection:
    """Aggregated media formats categorized for frontend display."""
    all_formats: List[ParsedFormat]
    video_formats: List[ParsedFormat]
    audio_formats: List[ParsedFormat]


def _determine_quality_label(height: Optional[int], fps: Optional[int], is_audio: bool, abr: Optional[float]) -> str:
    """Generate a premium quality label (e.g., 4K Ultra HD 60fps, 1080p Full HD)."""
    if is_audio:
        bitrate_str = f" ({int(abr)} kbps)" if abr and abr > 0 else ""
        return f"Lossless / HQ Audio{bitrate_str}"

    if not height:
        return "Standard Definition"

    fps_suffix = f" {int(fps)}fps" if fps and fps >= 50 else ""

    if height >= 2160:
        return f"4K Ultra HD (2160p{fps_suffix})"
    elif height >= 1440:
        return f"2K Quad HD (1440p{fps_suffix})"
    elif height >= 1080:
        return f"1080p Full HD{fps_suffix}"
    elif height >= 720:
        return f"720p HD{fps_suffix}"
    elif height >= 480:
        return f"480p SD{fps_suffix}"
    elif height >= 360:
        return f"360p Mobile{fps_suffix}"
    else:
        return f"{height}p"


def _estimate_filesize(raw_fmt: Dict[str, Any], duration: Optional[float]) -> Optional[int]:
    """Calculate or approximate filesize in bytes."""
    # 1. Exact filesize
    if raw_fmt.get("filesize") and raw_fmt["filesize"] > 0:
        return int(raw_fmt["filesize"])

    # 2. Approximate filesize provided by extractor
    if raw_fmt.get("filesize_approx") and raw_fmt["filesize_approx"] > 0:
        return int(raw_fmt["filesize_approx"])

    # 3. Calculate from duration and total bitrate (tbr in kbit/s)
    tbr = raw_fmt.get("tbr") or (
        (raw_fmt.get("vbr") or 0) + (raw_fmt.get("abr") or 0)
    )
    if tbr and duration and duration > 0 and tbr > 0:
        # tbr is in kilobits per second: (kbits * 1000 / 8) * duration
        calculated_bytes = int((float(tbr) * 1000.0 / 8.0) * float(duration))
        return calculated_bytes

    return None


def parse_media_formats(raw_formats: List[Dict[str, Any]], duration: Optional[float] = None) -> FormatsCollection:
    """Parse, filter, deduplicate, and tier raw yt-dlp formats."""
    parsed_videos: List[ParsedFormat] = []
    parsed_audios: List[ParsedFormat] = []
    seen_video_tiers = set()
    seen_audio_tiers = set()

    for fmt in raw_formats:
        fmt_id = str(fmt.get("format_id", ""))
        ext = fmt.get("ext", "mp4")
        vcodec = fmt.get("vcodec", "none") or "none"
        acodec = fmt.get("acodec", "none") or "none"
        height = fmt.get("height")
        width = fmt.get("width")
        fps = fmt.get("fps")
        tbr = fmt.get("tbr")
        abr = fmt.get("abr")
        direct_url = fmt.get("url")

        is_video = vcodec != "none"
        is_audio = acodec != "none"

        # Skip storyboards, m3u8 manifests without codecs, or non-media streams
        if not is_video and not is_audio:
            continue
        if vcodec == "none" and acodec == "none":
            continue

        is_video_only = is_video and not is_audio
        is_audio_only = is_audio and not is_video
        has_video_and_audio = is_video and is_audio

        filesize = _estimate_filesize(fmt, duration)
        filesize_formatted = format_bytes(filesize)

        if is_audio_only:
            label = _determine_quality_label(height=None, fps=None, is_audio=True, abr=abr)
            resolution = "Audio Only"
            
            # Deduplicate by approximate bitrate or extension
            abr_key = int(abr) if abr else 128
            tier_key = (ext, abr_key // 32)
            if tier_key in seen_audio_tiers:
                continue
            seen_audio_tiers.add(tier_key)

            parsed_audios.append(
                ParsedFormat(
                    format_id=fmt_id,
                    ext=ext,
                    resolution=resolution,
                    quality_label=label,
                    height=None,
                    fps=None,
                    filesize=filesize,
                    filesize_formatted=filesize_formatted,
                    vcodec=vcodec,
                    acodec=acodec,
                    is_video_only=False,
                    is_audio_only=True,
                    has_video_and_audio=False,
                    tbr=tbr,
                    url=direct_url,
                )
            )
        else:
            # Video or video+audio stream
            res_str = f"{width}x{height}" if width and height else (f"{height}p" if height else "Video")
            label = _determine_quality_label(height=height, fps=fps, is_audio=False, abr=abr)

            # Auto-synthesize best audio merge for video-only streams (e.g. 1080p/4K DASH)
            download_format_id = f"{fmt_id}+bestaudio/best" if is_video_only else fmt_id

            # Deduplicate by height, fps bracket, and container
            height_val = height or 0
            tier_key = (height_val, fps or 30, ext)
            if tier_key in seen_video_tiers:
                continue
            seen_video_tiers.add(tier_key)

            parsed_videos.append(
                ParsedFormat(
                    format_id=download_format_id,
                    ext=ext if ext in ["mp4", "mkv", "webm"] else "mp4",
                    resolution=res_str,
                    quality_label=label,
                    height=height,
                    fps=int(fps) if fps else None,
                    filesize=filesize,
                    filesize_formatted=filesize_formatted,
                    vcodec=vcodec,
                    acodec=acodec,
                    is_video_only=is_video_only,
                    is_audio_only=False,
                    has_video_and_audio=has_video_and_audio,
                    tbr=tbr,
                    url=direct_url,
                )
            )

    # Sort videos descending by height, then fps
    parsed_videos.sort(key=lambda x: (x.height or 0, x.fps or 0), reverse=True)

    # Sort audios descending by tbr or filesize
    parsed_audios.sort(key=lambda x: (x.tbr or 0, x.filesize or 0), reverse=True)

    all_combined = parsed_videos + parsed_audios
    return FormatsCollection(
        all_formats=all_combined,
        video_formats=parsed_videos,
        audio_formats=parsed_audios,
    )
