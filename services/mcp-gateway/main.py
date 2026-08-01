from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

import snapshots
import template_cache
from mcp_client import MCPClient
from schemas import ToolCallMeta, ToolCallRequest, ToolCallResponse
from size_guard import PayloadTooLarge, apply_size_guard

mcp_client = MCPClient()

metrics = {"tool_calls": 0, "truncation_events": 0, "errors": 0}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_client.connect()
    yield
    await mcp_client.close()


app = FastAPI(title="mcp-shell mcp-gateway", lifespan=lifespan)


@app.get("/tools/list")
async def tools_list():
    """Dynamic tool discovery for llm-agent — OpenAI-compatible function
    schema, so adding a tool to ecommerce-mcp-server needs no agent changes."""
    tools = await mcp_client.list_tools()
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


@app.post("/tools/call", response_model=ToolCallResponse)
async def tools_call(req: ToolCallRequest):
    metrics["tool_calls"] += 1
    try:
        result = await mcp_client.call_tool(req.tool_name, req.arguments)
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
        data, guard_meta = apply_size_guard(result.structured_content)
    except PayloadTooLarge as e:
        metrics["errors"] += 1
        raise HTTPException(status_code=413, detail=str(e)) from e

    if guard_meta["truncated"]:
        metrics["truncation_events"] += 1

    template_html = None
    cache_hit = False
    if resource_link_uri:
        template_html, cache_hit = await template_cache.get_template(
            resource_link_uri, lambda: mcp_client.read_resource(resource_link_uri)
        )

    snapshot_id = snapshots.new_snapshot_id()
    created_at = datetime.now(timezone.utc).isoformat()
    await snapshots.write_snapshot(
        snapshot_id=snapshot_id,
        chat_id=req.chat_id,
        msg_id=req.msg_id,
        template_ref=resource_link_uri,
        template_html=template_html,
        structured_content=data,
        meta=guard_meta,
        created_at=created_at,
    )

    return ToolCallResponse(
        snapshot_id=snapshot_id,
        template_ref=resource_link_uri,
        template_html=template_html,
        data=data,
        summary=summary,
        meta=ToolCallMeta(cache_hit=cache_hit, **guard_meta),
    )


@app.get("/health")
async def health():
    mcp_ok = await mcp_client.ping()
    redis_ok = await snapshots.ping()
    status = "ok" if mcp_ok and redis_ok else "degraded"
    body = {"status": status, "mcp_server": mcp_ok, "redis": redis_ok}
    return JSONResponse(body, status_code=200 if status == "ok" else 503)


@app.get("/metrics")
async def get_metrics():
    return {
        **metrics,
        "template_cache_hits": template_cache.hits,
        "template_cache_misses": template_cache.misses,
    }
