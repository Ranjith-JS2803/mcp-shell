from contextlib import asynccontextmanager

from fastapi import FastAPI

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
app.include_router(tools.router)
app.include_router(system.router)
app.include_router(history.router)
app.include_router(chat.router)
app.include_router(ws.router)
app.include_router(resources.router)
