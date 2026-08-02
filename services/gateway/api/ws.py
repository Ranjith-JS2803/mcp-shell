from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/{socket_id}")
async def websocket_endpoint(websocket: WebSocket, socket_id: str):
    """The frontend opens this once per session (using the same socket_id
    it then sends in every /chat request) and just listens — gateway is
    the only side that speaks first, pushing the final response once
    llm-agent replies."""
    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect(socket_id, websocket)
    try:
        while True:
            # Nothing expected from the frontend yet — this just keeps the
            # connection open and lets us detect a disconnect promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(socket_id)
