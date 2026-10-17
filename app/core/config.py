"""Application configuration management using Pydantic v2 Settings."""

import os
import shutil
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_ffmpeg_path(configured_path: str = "ffmpeg") -> str:
    """Resolve a valid FFmpeg executable path.
    
    Checks system PATH first, then falls back to bundled imageio-ffmpeg if available.
    """
    if configured_path and configured_path != "ffmpeg":
        resolved = shutil.which(configured_path) or configured_path
        if os.path.exists(resolved) or shutil.which(configured_path):
            return resolved

    system_which = shutil.which("ffmpeg")
    if system_which:
        return system_which

    try:
        import imageio_ffmpeg  # type: ignore
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and os.path.exists(bundled):
            return bundled
    except Exception:
        return "ffmpeg"

    return "ffmpeg"


def _resolve_ffprobe_path(configured_path: str = "ffprobe") -> str:
    """Resolve a valid FFprobe executable path."""
    if configured_path and configured_path != "ffprobe":
        resolved = shutil.which(configured_path) or configured_path
        if os.path.exists(resolved) or shutil.which(configured_path):
            return resolved

    system_which = shutil.which("ffprobe")
    if system_which:
        return system_which

    return "ffprobe"


class Settings(BaseSettings):
    """CBX-Stream Global Backend Settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Project Information
    PROJECT_NAME: str = "CBX Stream Universal Media Downloader Backend"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # CORS Settings
    CORS_ORIGINS: List[str] = ["*"]

    # Storage Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    TEMP_DIR: Path = Path("temp_downloads")
    LOG_DIR: Path = Path("logs")

    # Task Limits & Timeouts
    MAX_CONCURRENT_TASKS: int = 5
    DOWNLOAD_TIMEOUT_SECONDS: int = 1800
    MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024 * 1024  # 5 GB

    # Background Cleanup Worker
    CLEANUP_INTERVAL_SECONDS: int = 300  # Run every 5 minutes
    CLEANUP_TTL_SECONDS: int = 3600  # Purge files older than 1 hour

    # FFmpeg & FFprobe
    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"

    # Optional Network / Scraping Overrides
    PROXY_URL: Optional[str] = None
    COOKIES_FILE: Optional[str] = None
    COOKIES_FROM_BROWSER: Optional[str] = None
    NODE_PATH: Optional[str] = None

    def __init__(self, **values):
        super().__init__(**values)
        # Ensure directories exist
        if not self.TEMP_DIR.is_absolute():
            self.TEMP_DIR = self.BASE_DIR / self.TEMP_DIR
        if not self.LOG_DIR.is_absolute():
            self.LOG_DIR = self.BASE_DIR / self.LOG_DIR

        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Resolve FFmpeg binaries
        self.FFMPEG_PATH = _resolve_ffmpeg_path(self.FFMPEG_PATH)
        self.FFPROBE_PATH = _resolve_ffprobe_path(self.FFPROBE_PATH)

        # Auto-detect cookies.txt in root if not explicitly configured
        if not self.COOKIES_FILE:
            default_cookies = self.BASE_DIR / "cookies.txt"
            if default_cookies.exists():
                self.COOKIES_FILE = str(default_cookies)

        # Auto-detect Node.js for yt-dlp JavaScript challenge solver
        if not self.NODE_PATH:
            node_which = shutil.which("node")
            if node_which:
                self.NODE_PATH = node_which


# Singleton instance
settings = Settings()
