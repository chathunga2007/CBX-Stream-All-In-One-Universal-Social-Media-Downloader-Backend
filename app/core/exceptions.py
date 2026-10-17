"""Custom domain exceptions for CBX-Stream with structured error codes and HTTP mappings."""

from typing import Any, Dict, Optional


class CBXStreamException(Exception):
    """Base exception for CBX-Stream application."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class MediaExtractionError(CBXStreamException):
    """Raised when metadata or format extraction fails for a media URL."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="MEDIA_EXTRACTION_FAILED",
            details=details,
        )


class FFmpegProcessError(CBXStreamException):
    """Raised when an FFmpeg stream merge, transcoding, or trimming process fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="FFMPEG_PROCESS_FAILED",
            details=details,
        )


class DownloadTaskError(CBXStreamException):
    """Raised when an active media download fails or is interrupted."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="DOWNLOAD_TASK_FAILED",
            details=details,
        )


class TaskNotFoundError(CBXStreamException):
    """Raised when a requested task ID is not found in memory or storage."""

    def __init__(self, task_id: str):
        super().__init__(
            message=f"Task with ID '{task_id}' was not found or has expired.",
            status_code=404,
            error_code="TASK_NOT_FOUND",
            details={"task_id": task_id},
        )


class UnsupportedPlatformError(CBXStreamException):
    """Raised when a URL is not supported by any known extractor."""

    def __init__(self, url: str):
        super().__init__(
            message=f"No extractor available for the provided URL: {url}",
            status_code=400,
            error_code="UNSUPPORTED_PLATFORM",
            details={"url": url},
        )


class FileOperationError(CBXStreamException):
    """Raised when file streaming, compression, or cleanup encounters an error."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="FILE_OPERATION_FAILED",
            details=details,
        )


class InvalidTimestampError(CBXStreamException):
    """Raised when start or end timestamps for media trimming are invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="INVALID_TIMESTAMP",
            details=details,
        )


class CarouselExtractionError(CBXStreamException):
    """Raised when extracting multi-slide carousels or albums fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="CAROUSEL_EXTRACTION_FAILED",
            details=details,
        )
