"""All Pydantic v2 schemas for CBX-Stream requests, responses, and WebSocket events."""

from datetime import datetime, timezone
from typing import List, Optional, Literal, Any
from pydantic import BaseModel, Field, HttpUrl, ConfigDict, field_validator


class PlatformTheme(BaseModel):
    """Design tokens and visual branding for Chameleon Glass UI."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Platform identifier, e.g. youtube, instagram, tiktok")
    name: str = Field(..., description="Display name of the platform")
    icon: str = Field(..., description="Platform icon identifier")
    badge_text: str = Field(..., description="Visual badge label")
    primary_color: str = Field(..., description="Primary HEX brand color")
    secondary_color: str = Field(..., description="Secondary HEX color")
    accent_color: str = Field(..., description="Accent highlight color")
    gradient_css: str = Field(..., description="CSS linear-gradient background property")
    glass_border: str = Field(..., description="CSS border for glass card")
    glass_shadow: str = Field(..., description="CSS box-shadow for glass card glow")
    glow_color: str = Field(..., description="RGBA color for ambient glow")
    text_color: str = Field(default="#FFFFFF", description="Contrasting text color")


class MediaFormat(BaseModel):
    """Cleaned and categorized media stream format."""
    model_config = ConfigDict(extra="ignore")

    format_id: str = Field(..., description="yt-dlp format selector")
    ext: str = Field(..., description="Media extension (mp4, webm, mp3, m4a)")
    resolution: str = Field(..., description="Resolution string (e.g. 1920x1080, Audio Only)")
    quality_label: str = Field(..., description="Human-friendly label (e.g. 4K Ultra HD, 1080p Full HD)")
    height: Optional[int] = Field(None, description="Vertical pixel height")
    fps: Optional[int] = Field(None, description="Frames per second")
    filesize: Optional[int] = Field(None, description="Estimated or exact size in bytes")
    filesize_formatted: str = Field(..., description="Human-readable size (e.g. 15.4 MB)")
    vcodec: str = Field(default="none", description="Video codec name")
    acodec: str = Field(default="none", description="Audio codec name")
    is_video_only: bool = Field(default=False, description="True if stream contains only video")
    is_audio_only: bool = Field(default=False, description="True if stream contains only audio")
    has_video_and_audio: bool = Field(default=False, description="True if stream is progressive with audio")
    tbr: Optional[float] = Field(None, description="Total bitrate in kbit/s")
    url: Optional[str] = Field(None, description="Direct download URL if extractable")


class CarouselMediaItem(BaseModel):
    """Individual item in a multi-image or multi-video album/carousel."""
    model_config = ConfigDict(extra="ignore")

    index: int = Field(..., description="Sequential index in carousel (1-based)")
    url: str = Field(..., description="Direct high-resolution URL to the photo/video")
    thumbnail: Optional[str] = Field(None, description="Preview thumbnail URL")
    media_type: Literal["image", "video"] = Field(default="image", description="Media type")
    width: Optional[int] = Field(None, description="Media width in pixels")
    height: Optional[int] = Field(None, description="Media height in pixels")
    caption: Optional[str] = Field(None, description="Optional per-slide caption")


class MediaAnalyzeRequest(BaseModel):
    """Request schema for extracting metadata and formats from a media URL."""
    url: str = Field(..., min_length=4, description="Target social media URL")
    extract_flat: bool = Field(default=False, description="Fast shallow probe for playlists")


class MediaAnalyzeResponse(BaseModel):
    """Complete analyzed metadata and available formats for a given URL."""
    model_config = ConfigDict(extra="ignore")

    url: str = Field(..., description="Original requested URL")
    title: str = Field(..., description="Media title or post headline")
    description: Optional[str] = Field(None, description="Post text or description")
    uploader: Optional[str] = Field(None, description="Creator or channel name")
    uploader_id: Optional[str] = Field(None, description="Creator handle or channel ID")
    uploader_url: Optional[str] = Field(None, description="Creator profile URL")
    duration: Optional[float] = Field(None, description="Media duration in seconds")
    duration_formatted: str = Field(default="00:00", description="Formatted duration (MM:SS or HH:MM:SS)")
    thumbnail: Optional[str] = Field(None, description="HQ preview thumbnail URL")
    is_live: bool = Field(default=False, description="Whether the media is a live stream")
    view_count: Optional[int] = Field(None, description="Total view count")
    like_count: Optional[int] = Field(None, description="Total like count")
    upload_date: Optional[str] = Field(None, description="Upload timestamp or ISO date string")
    platform: PlatformTheme = Field(..., description="Platform branding and Chameleon Glass theme")
    formats: List[MediaFormat] = Field(default_factory=list, description="All deduplicated formats")
    video_formats: List[MediaFormat] = Field(default_factory=list, description="Categorized video formats")
    audio_formats: List[MediaFormat] = Field(default_factory=list, description="Categorized audio formats")
    is_carousel: bool = Field(default=False, description="Whether this post is a multi-item carousel")
    carousel_items: List[CarouselMediaItem] = Field(default_factory=list, description="Extracted carousel media items")


class BatchAnalyzeRequest(BaseModel):
    """Request schema for analyzing multiple media URLs concurrently."""
    urls: List[str] = Field(..., min_length=1, max_length=50, description="List of social media URLs")


class BatchAnalyzeItemResult(BaseModel):
    """Individual result inside a batch analysis response."""
    url: str
    success: bool
    data: Optional[MediaAnalyzeResponse] = None
    error: Optional[str] = None


class BatchAnalyzeResponse(BaseModel):
    """Aggregated response for batch URL analysis."""
    total: int = Field(..., description="Total URLs processed")
    successful: int = Field(..., description="Total successfully extracted URLs")
    failed: int = Field(..., description="Total failed extractions")
    items: List[BatchAnalyzeItemResult] = Field(..., description="Results per URL")


class DownloadRequest(BaseModel):
    """Request payload to initiate a media download job."""
    url: str = Field(..., min_length=4, description="Social media post or video URL")
    format_id: Optional[str] = Field(
        default="bestvideo+bestaudio/best",
        description="yt-dlp format selector or parsed format_id"
    )
    custom_filename: Optional[str] = Field(
        None,
        max_length=120,
        description="Optional custom base filename without extension"
    )
    extract_audio: bool = Field(
        default=False,
        description="If True, extract and convert to high-quality audio"
    )
    audio_format: Literal["mp3", "m4a", "flac", "wav", "opus"] = Field(
        default="mp3",
        description="Audio container format for audio extraction"
    )
    audio_quality: Literal["320", "256", "192", "128"] = Field(
        default="320",
        description="Audio bitrate in kbps"
    )
    embed_metadata: bool = Field(
        default=True,
        description="Embed artist, title, and album metadata"
    )
    embed_thumbnail: bool = Field(
        default=True,
        description="Embed cover art into MP3/M4A or video file"
    )
    start_time: Optional[str] = Field(
        None,
        description="Precision start timestamp for clipping (e.g. '00:15' or '15')"
    )
    end_time: Optional[str] = Field(
        None,
        description="Precision end timestamp for clipping (e.g. '01:30' or '90')"
    )


class DownloadTaskResponse(BaseModel):
    """Immediate response after queuing or initiating a download task."""
    task_id: str = Field(..., description="Unique task identifier (UUID)")
    status: Literal["queued", "downloading", "processing", "completed", "failed"] = Field(
        ...,
        description="Current task status"
    )
    message: str = Field(..., description="Human-readable status message")
    stream_url: Optional[str] = Field(None, description="Download/streaming URL once complete")
    ws_url: str = Field(..., description="WebSocket URL for live progress monitoring")


class DownloadProgressEvent(BaseModel):
    """Live progress update broadcast via WebSocket during media processing."""
    task_id: str
    status: Literal["queued", "downloading", "processing", "completed", "failed"]
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    downloaded_bytes: int = 0
    total_bytes: int = 0
    downloaded_formatted: str = "0 B"
    total_formatted: str = "0 B"
    speed: Optional[str] = None
    eta: Optional[str] = None
    filename: Optional[str] = None
    stream_url: Optional[str] = None
    error: Optional[str] = None

    @field_validator("downloaded_bytes", "total_bytes", mode="before")
    @classmethod
    def parse_bytes(cls, v: Any) -> int:
        if v is None:
            return 0
        try:
            return int(round(float(v)))
        except (ValueError, TypeError):
            return 0


class TrimRequest(BaseModel):
    """Request schema for precision timestamp trimming of media."""
    task_id: Optional[str] = Field(
        None,
        description="Existing completed task_id to trim from local cache"
    )
    url: Optional[str] = Field(
        None,
        description="Source URL to download and trim directly"
    )
    start_time: str = Field(..., description="Start timestamp (e.g. '00:30' or '30')")
    end_time: str = Field(..., description="End timestamp (e.g. '01:45' or '105')")
    format_id: Optional[str] = Field(None, description="Target format selector if downloading URL")
    extract_audio: bool = Field(default=False, description="Whether to trim as audio only")
    audio_format: Literal["mp3", "m4a", "wav", "flac"] = Field(default="mp3", description="Audio format")
    custom_filename: Optional[str] = Field(None, description="Custom output filename")


class TrimResponse(BaseModel):
    """Response schema for trimmed media result."""
    task_id: str
    status: str
    filename: str
    stream_url: str
    duration: float
    duration_formatted: str


class CarouselZipRequest(BaseModel):
    """Request payload to bundle multiple carousel items into a ZIP package."""
    media_urls: List[str] = Field(..., min_length=1, description="List of direct image/video URLs")
    custom_filename: Optional[str] = Field(None, max_length=100, description="Base name for zip archive")
    post_url: Optional[str] = Field(None, description="Original post URL for context")


class CarouselZipResponse(BaseModel):
    """Response schema after compiling a carousel ZIP package."""
    task_id: str
    zip_url: str
    file_count: int
    total_size_bytes: int
    total_size_formatted: str


class HealthResponse(BaseModel):
    """System health check and environmental status."""
    status: str = "healthy"
    version: str
    uptime_seconds: float
    active_tasks: int
    disk_free_gb: float
    disk_total_gb: float
    ffmpeg_available: bool
    ffmpeg_path: str
    python_version: str


class ErrorResponse(BaseModel):
    """Standardized error response returned for all API failures."""
    success: bool = False
    error_code: str
    detail: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
