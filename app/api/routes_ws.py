"""WebSocket endpoint for real-time task progress and status streaming."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.logger import get_logger
from app.services.ws_manager import ws_manager

logger = get_logger(__name__)

router = APIRouter(tags=["WebSocket Progress Streaming"])


@router.websocket("/ws/progress/{task_id}")
async def websocket_task_progress(websocket: WebSocket, task_id: str) -> None:
    """Stream live media extraction, download, and FFmpeg transcoding progress events."""
    await ws_manager.connect(task_id, websocket)
    try:
        while True:
            # Keepalive and client command listener
            data = await websocket.receive_text()
            if data.strip().lower() == "ping":
                await websocket.send_json({"type": "pong", "task_id": task_id})
    except WebSocketDisconnect:
        await ws_manager.disconnect(task_id, websocket)
    except Exception as e:
        logger.debug(f"[WS] Connection terminated for task {task_id}: {e}")
        await ws_manager.disconnect(task_id, websocket)
