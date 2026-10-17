"""Background worker to automatically purge expired temporary files in temp_downloads."""

import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Dict, Any

from app.core.config import settings
from app.core.logger import get_logger
from app.utils.file_helpers import format_bytes

logger = get_logger(__name__)


class CleanupService:
    """Manages periodic garbage collection of temporary downloads and cache artifacts."""

    def __init__(self) -> None:
        self.temp_dir = settings.TEMP_DIR
        self.ttl_seconds = settings.CLEANUP_TTL_SECONDS
        self.interval_seconds = settings.CLEANUP_INTERVAL_SECONDS
        self._task: asyncio.Task | None = None
        self._is_running = False

    def purge_expired_files(self) -> Dict[str, Any]:
        """Synchronously scan and remove files/folders older than TTL."""
        if not self.temp_dir.exists():
            return {"purged_count": 0, "reclaimed_bytes": 0, "reclaimed_formatted": "0 B"}

        now = time.time()
        purged_count = 0
        reclaimed_bytes = 0

        for item in self.temp_dir.iterdir():
            try:
                # Do not delete system files or .gitkeep
                if item.name.startswith("."):
                    continue

                mtime = item.stat().st_mtime
                age = now - mtime

                if age > self.ttl_seconds:
                    if item.is_file() or item.is_symlink():
                        size = item.stat().st_size
                        item.unlink(missing_ok=True)
                        purged_count += 1
                        reclaimed_bytes += size
                    elif item.is_dir():
                        dir_size = sum(
                            f.stat().st_size for f in item.glob("**/*") if f.is_file()
                        )
                        shutil.rmtree(item, ignore_errors=True)
                        purged_count += 1
                        reclaimed_bytes += dir_size

                    logger.debug(f"[CLEANUP] Purged expired temp artifact: {item.name}")
            except Exception as e:
                logger.warning(f"[CLEANUP] Error checking/purging {item.name}: {e}")

        if purged_count > 0:
            logger.info(
                f"[CLEANUP] Purged {purged_count} expired artifacts. "
                f"Reclaimed {format_bytes(reclaimed_bytes)}."
            )

        return {
            "purged_count": purged_count,
            "reclaimed_bytes": reclaimed_bytes,
            "reclaimed_formatted": format_bytes(reclaimed_bytes),
        }

    async def _cleanup_loop(self) -> None:
        """Periodic background cleanup loop."""
        logger.info(
            f"[CLEANUP] Worker started. Interval: {self.interval_seconds}s, TTL: {self.ttl_seconds}s"
        )
        while self._is_running:
            try:
                await asyncio.sleep(self.interval_seconds)
                if self._is_running:
                    await asyncio.to_thread(self.purge_expired_files)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CLEANUP] Unexpected error in cleanup cycle: {e}")

    def start(self) -> None:
        """Start the background cleanup loop."""
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the background cleanup loop gracefully."""
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug("[CLEANUP] Worker task cancellation acknowledged.")
        logger.info("[CLEANUP] Worker stopped.")


# Singleton cleanup worker
cleanup_service = CleanupService()
