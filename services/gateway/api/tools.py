from fastapi import APIRouter, HTTPException, Request

from components import chat_history
from components.mcp_gateway import PayloadTooLarge
from models.tool_call import ToolCallMeta, ToolCallRequest, ToolCallResponse

router = APIRouter()


@router.get("/tools/list")
async def tools_list(request: Request):
    """Dynamic tool discovery for llm-agent — OpenAI-compatible function
    schema, so adding a tool to ecommerce-mcp-server needs no agent changes."""
    gateway = request.app.state.gateway
    tools = await gateway.list_tools()
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.input_schema,
            },
        }
        for t in tools
    ]


@router.post("/tools/call", response_model=ToolCallResponse)
async def tools_call(req: ToolCallRequest, request: Request):
    gateway = request.app.state.gateway
    metrics = request.app.state.metrics

    metrics["tool_calls"] += 1
    try:
        result = await gateway.call_tool(req.tool_name, req.arguments)
    except Exception as e:
        metrics["errors"] += 1
        raise HTTPException(status_code=502, detail=f"MCP server call failed: {e}") from e

    summary = None
    resource_link_uri = None
    for block in result.content or []:
        if block.type == "text":
            summary = block.text
        elif block.type == "resource_link":
            resource_link_uri = block.uri

    if result.is_error:
        metrics["errors"] += 1
        raise HTTPException(status_code=502, detail=summary or "Tool call returned an error")

    try:
        data, guard_meta = gateway.apply_size_guard(result.structured_content)
    except PayloadTooLarge as e:
        metrics["errors"] += 1
        raise HTTPException(status_code=413, detail=str(e)) from e

    if guard_meta["truncated"]:
        metrics["truncation_events"] += 1

    template_html = None
    cache_hit = False
    if resource_link_uri:
        template_html, cache_hit = await gateway.get_template(resource_link_uri)

    artifact = {
        "template_ref": resource_link_uri,
        "template_html": template_html,
        "data": data,
        "meta": guard_meta,
    }
    await chat_history.update_artifact(req.chat_id, req.message_id, artifact)

    return ToolCallResponse(
        template_ref=resource_link_uri,
        template_html=template_html,
        data=data,
        summary=summary,
        meta=ToolCallMeta(cache_hit=cache_hit, **guard_meta),
    )
