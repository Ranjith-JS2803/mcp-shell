from contextlib import asynccontextmanager

from fastapi import FastAPI

import gateway_client
import llm_client
from models import Artifact, ChatRequest, ChatResponse
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


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Called only by gateway — gateway already created the history entry
    for this message before invoking us, so our only history write is
    the final reply.

    Every step below can fail independently (gateway/MCP server
    unreachable, the LLM call itself failing) — none of those should ever
    leave the user without a reply, or leave the history doc's reply
    stuck at null. Each failure degrades to a friendly fallback text
    instead of raising, and the reply write at the end always runs.
    """
    text = GENERIC_FAILURE_REPLY
    artifact = None

    try:
        tools = await gateway_client.list_tools()
        routing_prompt = load("routing").format(tools_block=build_tools_block(tools))
        decision = await llm_client.ask_json(routing_prompt, req.user_query)
        tool_call = decision.get("tool_call")

        if tool_call:
            tool_name = tool_call.get("name")
            arguments = tool_call.get("arguments") or {}

            try:
                result = await gateway_client.call_tool(tool_name, arguments, req.chat_id, req.message_id)
            except Exception:
                text = TOOL_UNAVAILABLE_REPLY
            else:
                try:
                    summary_prompt = load("summary").format(
                        tool_name=tool_name, tool_summary=result.get("summary") or ""
                    )
                    summary_decision = await llm_client.ask_json(summary_prompt, req.user_query)
                    text = summary_decision.get("reply") or result.get("summary") or GENERIC_FAILURE_REPLY
                except Exception:
                    # The tool call itself succeeded — fall back to its own
                    # summary rather than losing the artifact entirely.
                    text = result.get("summary") or GENERIC_FAILURE_REPLY

                if result.get("template_ref"):
                    artifact = Artifact(
                        template_ref=result["template_ref"],
                        template_html=result.get("template_html"),
                        data=result.get("data"),
                    )
        else:
            text = decision.get("reply") or GENERIC_FAILURE_REPLY
    except Exception:
        text = GENERIC_FAILURE_REPLY

    response = ChatResponse(
        chat_id=req.chat_id,
        message_id=req.message_id,
        type="artifact" if artifact else "text",
        text=text,
        artifact=artifact,
    )

    try:
        await gateway_client.update_history_reply(req.chat_id, req.message_id, response.text)
    except Exception:
        pass  # best-effort — the caller still gets the reply even if this write fails

    return response
