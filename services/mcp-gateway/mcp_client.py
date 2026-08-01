"""Owns the one persistent MCP session to ecommerce-mcp-server, opened at
gateway startup and reused for every request — not one session per call.
"""

import os
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://ecommerce-mcp-server:8002/mcp")


class MCPClient:
    def __init__(self, url: str = MCP_SERVER_URL) -> None:
        self.url = url
        self._stack = AsyncExitStack()
        self.session: ClientSession | None = None

    async def connect(self) -> None:
        read, write = await self._stack.enter_async_context(streamable_http_client(self.url))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

    async def close(self) -> None:
        await self._stack.aclose()
        self.session = None

    async def list_tools(self):
        assert self.session is not None, "MCPClient not connected"
        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, tool_name: str, arguments: dict) -> CallToolResult:
        assert self.session is not None, "MCPClient not connected"
        return await self.session.call_tool(tool_name, arguments)

    async def read_resource(self, uri: str) -> str:
        assert self.session is not None, "MCPClient not connected"
        result = await self.session.read_resource(uri)
        return result.contents[0].text

    async def ping(self) -> bool:
        try:
            await self.list_tools()
            return True
        except Exception:
            return False
