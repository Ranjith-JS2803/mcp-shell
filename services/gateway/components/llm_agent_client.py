"""The gateway's outbound call to llm-agent — the frontend never talks to
llm-agent directly. One persistent httpx client, opened at gateway startup
and reused, same pattern as the MCP session and the redis connection."""

import os

import httpx

LLM_AGENT_URL = os.environ.get("LLM_AGENT_URL", "http://llm-agent:8004")

_client: httpx.AsyncClient | None = None


async def connect() -> None:
    global _client
    _client = httpx.AsyncClient(base_url=LLM_AGENT_URL, timeout=60.0)


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


async def send_chat(chat_id: str, message_id: str, socket_id: str, user_query: str) -> dict:
    resp = await _client.post(
        "/chat",
        json={"chat_id": chat_id, "message_id": message_id, "socket_id": socket_id, "user_query": user_query},
    )
    resp.raise_for_status()
    return resp.json()
