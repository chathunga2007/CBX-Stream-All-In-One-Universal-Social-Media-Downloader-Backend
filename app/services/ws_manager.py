"""Real-time WebSocket connection manager and task progress broadcaster."""

import asyncio
import json
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from app.core.logger import get_logger
from app.schemas.media_schemas import DownloadProgressEvent

logger = get_logger(__name__)


class ConnectionManager:
    """Manages active WebSockets, cached task states, and thread-safe progress broadcasting."""

    def __init__(self) -> None:
        # Map task_id -> set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # In-memory store for the most recent progress event per task_id
        self.cached_states: Dict[str, Dict[str, Any]] = {}
        # Lock for connection state integrity
        self._lock = asyncio.Lock()
        # Main event loop reference
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store the running asyncio event loop reference."""
        self._loop = loop

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection for a given task_id."""
        await websocket.accept()
        async with self._lock:
            if task_id not in self.active_connections:
                self.active_connections[task_id] = set()
            self.active_connections[task_id].add(websocket)

        logger.debug(f"[WS] Client connected to task {task_id}. Active count: {len(self.active_connections[task_id])}")

        # Send cached state immediately if available
        if task_id in self.cached_states:
            try:
                await websocket.send_json(self.cached_states[task_id])
            except Exception as e:
                logger.warning(f"[WS] Failed to send cached state to new client: {e}")

    async def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket from active registry."""
        async with self._lock:
            if task_id in self.active_connections:
                self.active_connections[task_id].discard(websocket)
                if not self.active_connections[task_id]:
                    del self.active_connections[task_id]
        logger.debug(f"[WS] Client disconnected from task {task_id}")

    async def broadcast_async(self, task_id: str, event_data: Dict[str, Any]) -> None:
        """Broadcast progress event data to all connected clients for a task."""
        # Cache the latest state
        self.cached_states[task_id] = event_data

        connections = self.active_connections.get(task_id, set()).copy()
        if not connections:
            return

        dead_connections: Set[WebSocket] = set()
        for connection in connections:
            try:
                await connection.send_json(event_data)
            except (WebSocketDisconnect, RuntimeError):
                dead_connections.add(connection)
            except Exception as e:
                logger.warning(f"[WS] Error sending to websocket: {e}")
                dead_connections.add(connection)

        if dead_connections:
            async with self._lock:
                if task_id in self.active_connections:
                    for dead in dead_connections:
                        self.active_connections[task_id].discard(dead)
                    if not self.active_connections[task_id]:
                        del self.active_connections[task_id]

    def broadcast_sync(self, task_id: str, event: DownloadProgressEvent | Dict[str, Any]) -> None:
        """Thread-safe dispatch from synchronous threads (e.g., yt-dlp progress hook)."""
        data = event.model_dump() if isinstance(event, DownloadProgressEvent) else event
        self.cached_states[task_id] = data

        loop = self._loop
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast_async(task_id, data), loop)

    def get_latest_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the last known progress event for a task."""
        return self.cached_states.get(task_id)

    def clear_task(self, task_id: str) -> None:
        """Clean up memory for a completed or purged task."""
        self.cached_states.pop(task_id, None)
        self.active_connections.pop(task_id, None)


# Singleton connection manager instance
ws_manager = ConnectionManager()
