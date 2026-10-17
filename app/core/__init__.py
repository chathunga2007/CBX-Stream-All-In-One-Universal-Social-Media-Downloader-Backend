"""Core configuration, exceptions, and logging for CBX-Stream."""

from app.core.config import settings
from app.core.exceptions import (
    CBXStreamException,
    MediaExtractionError,
    FFmpegProcessError,
    DownloadTaskError,
    TaskNotFoundError,
    UnsupportedPlatformError,
    FileOperationError,
    InvalidTimestampError,
    CarouselExtractionError,
)
from app.core.logger import get_logger

__all__ = [
    "settings",
    "CBXStreamException",
    "MediaExtractionError",
    "FFmpegProcessError",
    "DownloadTaskError",
    "TaskNotFoundError",
    "UnsupportedPlatformError",
    "FileOperationError",
    "InvalidTimestampError",
    "CarouselExtractionError",
    "get_logger",
]
