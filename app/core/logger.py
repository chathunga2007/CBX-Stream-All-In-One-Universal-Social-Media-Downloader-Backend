"""Structured console and rotating file logger for CBX-Stream."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.core.config import settings


class ColorFormatter(logging.Formatter):
    """Custom colorized console log formatter."""

    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD_RED = "\033[1;91m"
    RESET = "\033[0m"

    FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s"

    LEVEL_COLORS = {
        logging.DEBUG: CYAN,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
        log_fmt = f"{color}%(asctime)s | %(levelname)-8s{self.RESET} | %(name)s:%(lineno)d - %(message)s"
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def setup_root_logger() -> None:
    """Configure the root logger with both console and rotating file handlers."""
    root_logger = logging.getLogger()
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers on reload
    if root_logger.handlers:
        return

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColorFormatter())
    root_logger.addHandler(console_handler)

    # Rotating File Handler
    log_file: Path = settings.LOG_DIR / "cbx_stream.log"
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(process)d | %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=10 * 1024 * 1024,  # 10 MB per log file
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Retrieve a configured logger instance for a given module name."""
    if not logging.getLogger().handlers:
        setup_root_logger()
    return logging.getLogger(name)
