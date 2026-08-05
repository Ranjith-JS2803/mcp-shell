import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import chat, history, resources, system, tools, ws
from components import llm_agent_client
from components.mcp_gateway import MCPGateway
from components.websocket_manager import WebSocketManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    gateway = MCPGateway()
    await gateway.connect()
    await llm_agent_client.connect()
    app.state.gateway = gateway
    app.state.ws_manager = WebSocketManager()
    app.state.metrics = {"tool_calls": 0, "truncation_events": 0, "errors": 0}
    yield
    await llm_agent_client.close()
    await gateway.close()


app = FastAPI(title="mcp-shell gateway", lifespan=lifespan)

# The frontend is a separate origin (dev server on :3000, or wherever the
# built app is served from) — without this, the browser blocks every
# request the frontend makes, including the WebSocket's initial handshake.
_frontend_origins = os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tools.router)
app.include_router(system.router)
app.include_router(history.router)
app.include_router(chat.router)
app.include_router(ws.router)
app.include_router(resources.router)
