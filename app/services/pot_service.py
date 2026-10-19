"""Background supervisor for YouTube PO Token generator server (bgutil)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional
import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

POT_PORT = 4416
POT_PING_URL = f"http://127.0.0.1:{POT_PORT}/ping"


class PotService:
    """Manages the background Node.js bgutil server for YouTube BotGuard PO token resolution."""

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._server_dir = settings.BASE_DIR / "bgutil-pot-server" / "server"
        self._server_script = self._server_dir / "build" / "main.js"

    def is_running(self) -> bool:
        """Check if the PO token server is reachable via ping."""
        try:
            with httpx.Client(timeout=1.5) as client:
                res = client.get(POT_PING_URL)
                return res.status_code == 200
        except Exception:
            return False

    def start(self) -> None:
        """Launch the POT generator server if not already running."""
        if self.is_running():
            logger.info(f"[POT-SERVER] Already active on port {POT_PORT}.")
            return

        node_path = None
        if settings.NODE_PATH and os.path.exists(settings.NODE_PATH):
            node_path = settings.NODE_PATH
        elif shutil.which("node"):
            node_path = shutil.which("node")

        if not node_path:
            logger.warning("[POT-SERVER] Node.js not detected on system. Automated YouTube PO tokens disabled.")
            return

        if not self._server_script.exists():
            logger.warning(f"[POT-SERVER] Script {self._server_script} not found. Skipping auto-start.")
            return

        try:
            logger.info(f"[POT-SERVER] Spawning PO Token Provider on port {POT_PORT} via {node_path}...")
            # Run without opening extra console window on Windows
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            self._proc = subprocess.Popen(
                [node_path, str(self._server_script), "-p", str(POT_PORT)],
                cwd=str(self._server_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            logger.info(f"[POT-SERVER] Background worker spawned with PID {self._proc.pid}.")
        except Exception as e:
            logger.warning(f"[POT-SERVER] Failed to spawn token provider: {e}")

    def stop(self) -> None:
        """Cleanly terminate the token provider subprocess."""
        if self._proc:
            logger.info(f"[POT-SERVER] Stopping PO Token Provider PID {self._proc.pid}...")
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None


# Singleton instance
pot_service = PotService()
