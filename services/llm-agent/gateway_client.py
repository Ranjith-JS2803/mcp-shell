"""The only thing in llm-agent that talks HTTP to gateway — tool discovery,
tool calls, and the one history write llm-agent owns (the final reply;
gateway creates the entry itself before ever calling llm-agent). One
persistent httpx client, opened at startup and reused, same pattern as
gateway's own MCP session."""

import httpx

from config import GATEWAY_URL

_client: httpx.AsyncClient | None = None


async def connect() -> None:
    global _client
    _client = httpx.AsyncClient(base_url=GATEWAY_URL, timeout=30.0)


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


async def list_tools() -> list[dict]:
    resp = await _client.get("/tools/list")
    resp.raise_for_status()
    return resp.json()


async def call_tool(tool_name: str, arguments: dict, chat_id: str, message_id: str) -> dict:
    resp = await _client.post(
        "/tools/call",
        json={"tool_name": tool_name, "arguments": arguments, "chat_id": chat_id, "message_id": message_id},
    )
    resp.raise_for_status()
    return resp.json()


async def update_history_reply(chat_id: str, message_id: str, reply: str) -> None:
    resp = await _client.patch(f"/history/{chat_id}/{message_id}", json={"reply": reply})
    resp.raise_for_status()
