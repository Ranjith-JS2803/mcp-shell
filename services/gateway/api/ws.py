from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/{socket_id}")
async def websocket_endpoint(websocket: WebSocket, socket_id: str):
    """Outbound-only — frontend listens, never sends requests here."""
    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect(socket_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # discarded; just detects disconnect
    except WebSocketDisconnect:
        ws_manager.disconnect(socket_id)
