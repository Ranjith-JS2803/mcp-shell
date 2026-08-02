"""Frontend-facing WebSocket connection registry and push primitive.

Scope today: register/unregister a socket_id's connection, and push a
JSON message to it if still connected. POST /chat uses this to deliver
the final response asynchronously — the frontend gets an immediate ack
from the HTTP call, and the real answer arrives over this socket once
llm-agent replies. The message shape isn't assumed here; pagination and
real token streaming can reuse this same push() primitive later.
"""

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
        """Best-effort — if the socket was never opened or already dropped,
        this is a no-op rather than an error. Whatever called push() (e.g.
        POST /chat) has already persisted the result to Redis, so nothing
        is lost even when delivery here fails."""
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
