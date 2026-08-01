from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import system, tools
from components.mcp_gateway import MCPGateway


@asynccontextmanager
async def lifespan(app: FastAPI):
    gateway = MCPGateway()
    await gateway.connect()
    app.state.gateway = gateway
    app.state.metrics = {"tool_calls": 0, "truncation_events": 0, "errors": 0}
    yield
    await gateway.close()


app = FastAPI(title="mcp-shell gateway", lifespan=lifespan)
app.include_router(tools.router)
app.include_router(system.router)
