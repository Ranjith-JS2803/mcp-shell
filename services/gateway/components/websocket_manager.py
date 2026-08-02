"""Outbound-only WebSocket registry: gateway pushes, frontend only listens."""

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, socket_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[socket_id] = websocket

    def disconnect(self, socket_id: str) -> None:
        self._connections.pop(socket_id, None)

    def is_connected(self, socket_id: str) -> bool:
        return socket_id in self._connections

    async def push(self, socket_id: str, message: dict) -> bool:
        """Best-effort — no-op if not connected, never raises."""
        websocket = self._connections.get(socket_id)
        if websocket is None:
            logger.warning("push to unknown/disconnected socket_id=%s dropped", socket_id)
            return False
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            logger.warning("push to socket_id=%s failed, dropping connection", socket_id)
            self._connections.pop(socket_id, None)
            return False
