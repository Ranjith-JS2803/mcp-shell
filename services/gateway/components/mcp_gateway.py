"""Everything involved in bridging a tool call to ecommerce-mcp-server:
the persistent MCP session, the in-memory template cache, and the payload
size guard. Grouped in one file since they're all "the MCP-gateway logic"
— one cohesive responsibility, even though it does three things.
"""

import asyncio
import json
import os
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://ecommerce-mcp-server:8002/mcp")

MAX_ITEMS = 500
MAX_BYTES = 256 * 1024


class PayloadTooLarge(Exception):
    def __init__(self, payload_bytes: int) -> None:
        self.payload_bytes = payload_bytes
        super().__init__(f"structuredContent is {payload_bytes} bytes, exceeds {MAX_BYTES}")


class MCPGateway:
    """Owns the one persistent MCP session, opened at gateway startup and
    reused for every request — not one session per call."""

    def __init__(self, url: str = MCP_SERVER_URL) -> None:
        self.url = url
        self._stack = AsyncExitStack()
        self.session: ClientSession | None = None
        self._template_cache: dict[str, str] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    # -- session lifecycle --------------------------------------------------

    async def connect(self, retries: int = 15, delay: float = 2.0) -> None:
        """Retries instead of crashing gateway's startup — depends_on only
        gates container start order, not "the MCP server can actually
        handle a session.initialize() yet"."""
        last_exc: Exception | None = None
        for attempt in range(retries):
            stack = AsyncExitStack()
            try:
                read, write = await stack.enter_async_context(streamable_http_client(self.url))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
            except Exception as e:
                last_exc = e
                await stack.aclose()
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                continue
            self._stack = stack
            self.session = session
            return
        raise RuntimeError(f"Could not connect to MCP server at {self.url} after {retries} attempts") from last_exc

    async def close(self) -> None:
        await self._stack.aclose()
        self.session = None

    async def ping(self) -> bool:
        try:
            await self.list_tools()
            return True
        except Exception:
            return False

    # -- MCP calls ------------------------------------------------------------

    async def list_tools(self):
        assert self.session is not None, "MCPGateway not connected"
        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, tool_name: str, arguments: dict) -> CallToolResult:
        assert self.session is not None, "MCPGateway not connected"
        return await self.session.call_tool(tool_name, arguments)

    async def read_resource(self, uri: str) -> str:
        assert self.session is not None, "MCPGateway not connected"
        result = await self.session.read_resource(uri)
        return result.contents[0].text

    # -- template cache ---------------------------------------------------------

    async def get_template(self, uri: str) -> tuple[str, bool]:
        """Returns (html, cache_hit). Warm after the first tools/call that
        references a given template — later calls skip resources/read."""
        if uri in self._template_cache:
            self.cache_hits += 1
            return self._template_cache[uri], True
        self.cache_misses += 1
        html = await self.read_resource(uri)
        self._template_cache[uri] = html
        return html, False

    # -- size guard ---------------------------------------------------------------

    @staticmethod
    def apply_size_guard(structured_content: dict | None) -> tuple[dict | None, dict]:
        """Catches a careless tool response before it reaches the LLM
        context or the snapshot store: arrays capped at MAX_ITEMS, whole
        payload rejected above MAX_BYTES."""
        if structured_content is None:
            return None, {"truncated": False, "payload_bytes": 0}

        truncated = False
        guarded = {}
        for key, value in structured_content.items():
            if isinstance(value, list) and len(value) > MAX_ITEMS:
                guarded[key] = value[:MAX_ITEMS]
                truncated = True
            else:
                guarded[key] = value

        payload_bytes = len(json.dumps(guarded, default=str).encode())
        if payload_bytes > MAX_BYTES:
            raise PayloadTooLarge(payload_bytes)

        return guarded, {"truncated": truncated, "payload_bytes": payload_bytes}
