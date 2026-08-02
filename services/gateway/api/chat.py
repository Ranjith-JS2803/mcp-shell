from fastapi import APIRouter, BackgroundTasks, Request

from components import chat_history, llm_agent_client
from components.websocket_manager import WebSocketManager
from models.chat import ChatRequest

router = APIRouter()

AGENT_UNAVAILABLE_REPLY = "Sorry, the assistant is temporarily unavailable. Please try again shortly."


def _fallback_response(req: ChatRequest, text: str) -> dict:
    return {"chat_id": req.chat_id, "message_id": req.message_id, "type": "text", "text": text, "artifact": None}


async def _process_chat(req: ChatRequest, ws_manager: WebSocketManager) -> None:
    """Runs after the ack is sent — calls llm-agent, pushes the reply over the socket."""
    try:
        response = await llm_agent_client.send_chat(req.chat_id, req.message_id, req.socket_id, req.user_query)
    except Exception:
        try:
            await chat_history.update_reply(req.chat_id, req.message_id, AGENT_UNAVAILABLE_REPLY)
        except Exception:
            pass
        response = _fallback_response(req, AGENT_UNAVAILABLE_REPLY)

    await ws_manager.push(req.socket_id, response)


@router.post("/chat")
async def chat(req: ChatRequest, request: Request, background_tasks: BackgroundTasks) -> dict:
    """Creates the history entry, hands off to llm-agent in the background, acks immediately."""
    try:
        await chat_history.create_message(req.chat_id, req.message_id, req.user_query)
    except Exception:
        pass  # best-effort — still try to serve the user even if Redis is down

    background_tasks.add_task(_process_chat, req, request.app.state.ws_manager)
    return {"status": "accepted", "chat_id": req.chat_id, "message_id": req.message_id}
