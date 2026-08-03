import json

from fastapi import APIRouter, HTTPException, Request

from components.mcp_gateway import PayloadTooLarge

router = APIRouter()


@router.get("/resource")
async def get_resource(ref: str, request: Request):
    """Frontend's pagination/drill-down relay. A template's postMessage
    request_data carries a next_ref it got from the mcp-server — frontend
    forwards that ref here verbatim, gateway resolves it via resources/read.
    Frontend never talks to the MCP server directly.
    """
    gateway = request.app.state.gateway
    metrics = request.app.state.metrics

    try:
        raw = await gateway.read_resource(ref)
    except Exception as e:
        metrics["errors"] += 1
        raise HTTPException(status_code=502, detail=f"MCP server call failed: {e}") from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        metrics["errors"] += 1
        raise HTTPException(status_code=502, detail=f"Resource {ref} did not return JSON") from e

    try:
        guarded, guard_meta = gateway.apply_size_guard(data)
    except PayloadTooLarge as e:
        metrics["errors"] += 1
        raise HTTPException(status_code=413, detail=str(e)) from e

    if guard_meta["truncated"]:
        metrics["truncation_events"] += 1

    return {"data": guarded, "meta": guard_meta}
