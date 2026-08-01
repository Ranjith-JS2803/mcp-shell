from contextlib import asynccontextmanager

from fastapi import FastAPI

import gateway_client
import llm_client
from models import Artifact, ChatRequest, ChatResponse
from prompts.loader import build_tools_block, load


@asynccontextmanager
async def lifespan(app: FastAPI):
    await gateway_client.connect()
    yield
    await gateway_client.close()


app = FastAPI(title="mcp-shell llm-agent", lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    await gateway_client.create_history_message(req.chat_id, req.message_id, req.user_query)

    tools = await gateway_client.list_tools()
    routing_prompt = load("routing").format(tools_block=build_tools_block(tools))
    decision = await llm_client.ask_json(routing_prompt, req.user_query)

    tool_call = decision.get("tool_call")
    artifact = None

    if tool_call:
        tool_name = tool_call.get("name")
        arguments = tool_call.get("arguments") or {}
        result = await gateway_client.call_tool(tool_name, arguments, req.chat_id, req.message_id)

        summary_prompt = load("summary").format(tool_name=tool_name, tool_summary=result.get("summary") or "")
        summary_decision = await llm_client.ask_json(summary_prompt, req.user_query)
        text = summary_decision.get("reply") or result.get("summary") or ""

        if result.get("template_ref"):
            artifact = Artifact(
                template_ref=result["template_ref"],
                template_html=result.get("template_html"),
                data=result.get("data"),
            )
    else:
        text = decision.get("reply") or ""

    response = ChatResponse(
        chat_id=req.chat_id,
        message_id=req.message_id,
        type="artifact" if artifact else "text",
        text=text,
        artifact=artifact,
    )

    await gateway_client.update_history_reply(req.chat_id, req.message_id, response.text)
    return response
