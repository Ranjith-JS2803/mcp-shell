import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

import gateway_client
import llm_client
from models import ChatRequest
from prompts.loader import build_tools_block, load

TOOL_UNAVAILABLE_REPLY = "I'm having trouble reaching the data service right now. Please try again in a moment."
GENERIC_FAILURE_REPLY = "Something went wrong while I was processing that. Please try again."


@asynccontextmanager
async def lifespan(app: FastAPI):
    await gateway_client.connect()
    yield
    await gateway_client.close()


app = FastAPI(title="mcp-shell llm-agent", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


def _event(event: str, **fields) -> str:
    return json.dumps({"event": event, **fields}) + "\n"


async def _stream_chat(req: ChatRequest):
    """Newline-delimited JSON events: any number of `chunk`s (the reply,
    streamed token by token as the LLM generates it) followed by exactly
    one `final` (the complete ChatResponse-shaped payload, once the reply
    is fully assembled and the history write has been attempted).

    Every step can fail independently (gateway/MCP server unreachable,
    either LLM call failing) — none of those should leave the user
    without a reply, or leave the history doc's reply stuck at null.
    """
    artifact = None
    tool_name = None
    tool_summary = ""
    tool_call = None
    tool_failed = False

    try:
        tools = await gateway_client.list_tools()
        routing_prompt = load("routing").format(tools_block=build_tools_block(tools))
        decision = await llm_client.ask_json(routing_prompt, req.user_query)
        tool_call = decision.get("tool_call")
    except Exception:
        tool_failed = True

    if tool_call and not tool_failed:
        tool_name = tool_call.get("name")
        arguments = tool_call.get("arguments") or {}
        try:
            result = await gateway_client.call_tool(tool_name, arguments, req.chat_id, req.message_id)
            tool_summary = result.get("summary") or ""
            if result.get("template_ref"):
                artifact = {
                    "template_ref": result["template_ref"],
                    "template_html": result.get("template_html"),
                    "data": result.get("data"),
                }
        except Exception:
            tool_failed = True

    full_text = ""
    if tool_failed:
        full_text = TOOL_UNAVAILABLE_REPLY if tool_call else GENERIC_FAILURE_REPLY
        yield _event("chunk", text=full_text)
    else:
        tool_context = (
            f"You already ran the tool '{tool_name}' and got this result: {tool_summary}. "
            "Describe what it shows in one sentence — do not restate every number, "
            "the artifact itself will render them."
            if tool_name
            else ""
        )
        reply_prompt = load("reply").format(tool_context=tool_context)
        try:
            async for piece in llm_client.stream_text(reply_prompt, req.user_query):
                full_text += piece
                yield _event("chunk", text=piece)
        except Exception:
            full_text = tool_summary or GENERIC_FAILURE_REPLY
            yield _event("chunk", text=full_text)

    response = {
        "chat_id": req.chat_id,
        "message_id": req.message_id,
        "type": "artifact" if artifact else "text",
        "text": full_text,
        "artifact": artifact,
    }

    try:
        await gateway_client.update_history_reply(req.chat_id, req.message_id, full_text)
    except Exception:
        pass  # best-effort — the caller still gets the reply even if this write fails

    yield _event("final", response=response)


@app.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    """Called only by gateway — gateway already created the history entry
    for this message before invoking us."""
    return StreamingResponse(_stream_chat(req), media_type="application/x-ndjson")
