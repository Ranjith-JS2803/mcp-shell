from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from components import chat_history

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    gateway = request.app.state.gateway
    mcp_ok = await gateway.ping()
    redis_ok = await chat_history.ping()
    status = "ok" if mcp_ok and redis_ok else "degraded"
    body = {"status": status, "mcp_server": mcp_ok, "redis": redis_ok}
    return JSONResponse(body, status_code=200 if status == "ok" else 503)


@router.get("/metrics")
async def get_metrics(request: Request):
    gateway = request.app.state.gateway
    metrics = request.app.state.metrics
    return {
        **metrics,
        "template_cache_hits": gateway.cache_hits,
        "template_cache_misses": gateway.cache_misses,
    }
