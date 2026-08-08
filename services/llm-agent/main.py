import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

import gateway_client
import llm_client
from models import ChatRequest
from prompts.loader import build_tools_block, load

logger = logging.getLogger("llm-agent")

TOOL_UNAVAILABLE_REPLY = "I'm having trouble reaching the data service right now. Please try again in a moment."
GENERIC_FAILURE_REPLY = "Something went wrong while I was processing that. Please try again."
MAX_TITLE_WORDS = 5


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


def _clip_to_words(text: str, max_words: int) -> str:
    words = text.strip().split()
    return " ".join(words[:max_words])


async def _stream_chat(req: ChatRequest):
    """Newline-delimited JSON events: optionally a run of `title_chunk`s +
    one `title_done` (only on a chat's first message), then any number of
    `chunk`s (the reply, streamed token by token) followed by exactly one
    `final` (the complete ChatResponse-shaped payload, once the reply is
    fully assembled and the history write has been attempted).

    Every step can fail independently (gateway/MCP server unreachable,
    either LLM call failing) — none of those should leave the user
    without a reply, or leave the history doc's reply stuck at null.
    """
    if req.is_first_message:
        try:
            title = ""
            async for piece in llm_client.stream_text(load("title"), req.user_query):
                title += piece
                yield _event("title_chunk", text=piece)
            yield _event("title_done", title=_clip_to_words(title, MAX_TITLE_WORDS))
        except Exception:
            logger.exception("title generation failed for chat_id=%s message_id=%s", req.chat_id, req.message_id)
            # Non-fatal — the frontend already has a placeholder title from
            # the user's own message; just move on without a title_done.

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
        logger.exception("routing decision failed for chat_id=%s message_id=%s", req.chat_id, req.message_id)
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
            logger.exception(
                "tool call failed for chat_id=%s message_id=%s tool=%s args=%s",
                req.chat_id, req.message_id, tool_name, arguments,
            )
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
            logger.exception("reply streaming failed for chat_id=%s message_id=%s", req.chat_id, req.message_id)
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
