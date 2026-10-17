"""File name sanitization, timestamp parsing, byte formatting, and path security helpers."""

import re
from pathlib import Path
from typing import Union
from app.core.exceptions import InvalidTimestampError, FileOperationError

# Reserved filenames in Windows
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# Illegal characters for filenames across Windows, macOS, and Linux
ILLEGAL_CHARS_REGEX = re.compile(r'[\\/*?:"<>|\x00-\x1f\x7f]')


def sanitize_filename(filename: str, max_length: int = 150) -> str:
    """Sanitize a proposed filename to be cross-platform safe.
    
    Removes invalid characters, handles Windows reserved names, and constrains length.
    """
    if not filename:
        return "cbx_download"

    # Replace illegal characters with underscore
    clean = ILLEGAL_CHARS_REGEX.sub("_", filename)
    
    # Collapse multiple underscores or spaces
    clean = re.sub(r"[\s_]+", "_", clean).strip(" ._")

    if not clean:
        clean = "cbx_download"

    # Check Windows reserved base names
    base_name = clean.split(".")[0].upper()
    if base_name in RESERVED_NAMES:
        clean = f"cbx_{clean}"

    # Constrain length while keeping extension
    path_obj = Path(clean)
    suffix = path_obj.suffix
    stem = path_obj.stem

    if len(clean) > max_length:
        max_stem_len = max(10, max_length - len(suffix))
        clean = f"{stem[:max_stem_len]}{suffix}"

    return clean


def format_bytes(size_bytes: Union[int, float, None]) -> str:
    """Convert a byte count into a human-readable string (e.g., 14.52 MB)."""
    if size_bytes is None or size_bytes < 0:
        return "Unknown"

    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if size < 1024.0 or unit == "PB":
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0

    return f"{size:.2f} PB"


def parse_timestamp(timestamp: Union[str, int, float]) -> float:
    """Parse a timestamp string into total seconds.
    
    Supports:
      - 'HH:MM:SS' or 'HH:MM:SS.mmm'
      - 'MM:SS' or 'MM:SS.mmm'
      - Pure seconds as string, int, or float ('95', '95.5', 95)
    """
    if isinstance(timestamp, (int, float)):
        if timestamp < 0:
            raise InvalidTimestampError(f"Timestamp cannot be negative: {timestamp}")
        return float(timestamp)

    ts_str = str(timestamp).strip()
    if not ts_str:
        raise InvalidTimestampError("Empty timestamp provided")

    # If it's a direct numeric string
    try:
        val = float(ts_str)
        if val < 0:
            raise InvalidTimestampError(f"Timestamp cannot be negative: {ts_str}")
        return val
    except ValueError:
        is_formatted_timestamp = True

    # Colon separated format HH:MM:SS or MM:SS
    parts = ts_str.split(":")
    try:
        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            if minutes < 0 or seconds < 0:
                raise ValueError
            return minutes * 60 + seconds
        elif len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            if hours < 0 or minutes < 0 or seconds < 0:
                raise ValueError
            return hours * 3600 + minutes * 60 + seconds
        else:
            raise ValueError
    except ValueError:
        raise InvalidTimestampError(
            f"Invalid timestamp format: '{ts_str}'. Expected 'HH:MM:SS', 'MM:SS', or seconds."
        )


def format_duration(seconds: Union[int, float, None]) -> str:
    """Format total seconds into a clean duration string ('03:45' or '01:25:30')."""
    if seconds is None or seconds < 0:
        return "00:00"

    total_secs = int(round(seconds))
    hrs = total_secs // 3600
    mins = (total_secs % 3600) // 60
    secs = total_secs % 60

    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def format_speed(bytes_per_sec: Union[int, float, None]) -> str:
    """Format download speed in bytes/sec into a clean readable string."""
    if bytes_per_sec is None or bytes_per_sec <= 0:
        return "-- KB/s"
    return f"{format_bytes(bytes_per_sec)}/s"


def get_safe_filepath(base_dir: Path, filename: str) -> Path:
    """Resolve a filename inside base_dir ensuring no directory traversal escapes base_dir."""
    clean_name = sanitize_filename(filename)
    resolved_path = (base_dir / clean_name).resolve()
    base_resolved = base_dir.resolve()

    try:
        resolved_path.relative_to(base_resolved)
    except ValueError:
        raise FileOperationError(
            message=f"Path traversal detected: {filename}",
            details={"filename": filename},
        )
    return resolved_path
