from fastapi import APIRouter

from components import chat_history, llm_agent_client
from models.chat import ChatRequest

router = APIRouter()

AGENT_UNAVAILABLE_REPLY = "Sorry, the assistant is temporarily unavailable. Please try again shortly."


def _fallback_response(req: ChatRequest, text: str) -> dict:
    return {"chat_id": req.chat_id, "message_id": req.message_id, "type": "text", "text": text, "artifact": None}


@router.post("/chat")
async def chat(req: ChatRequest) -> dict:
    """The frontend's only entrypoint for a chat turn. Creates the history
    entry here, then hands off to llm-agent — the frontend never calls
    llm-agent directly.

    Always returns a normal ChatResponse-shaped body, even on failure —
    the frontend should never have to special-case a raw error status,
    and the chat-history doc should never be left with reply: null
    forever just because a downstream service was unreachable.
    """
    try:
        await chat_history.create_message(req.chat_id, req.message_id, req.user_query)
    except Exception:
        pass  # best-effort — still try to serve the user even if Redis is down

    try:
        return await llm_agent_client.send_chat(req.chat_id, req.message_id, req.socket_id, req.user_query)
    except Exception:
        try:
            await chat_history.update_reply(req.chat_id, req.message_id, AGENT_UNAVAILABLE_REPLY)
        except Exception:
            pass
        return _fallback_response(req, AGENT_UNAVAILABLE_REPLY)
