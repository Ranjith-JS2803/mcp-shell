"""The gateway's outbound call to llm-agent — the frontend never talks to
llm-agent directly. One persistent httpx client, opened at gateway startup
and reused, same pattern as the MCP session and the redis connection."""

import json
import os
from collections.abc import AsyncIterator

import httpx

LLM_AGENT_URL = os.environ.get("LLM_AGENT_URL", "http://llm-agent:8004")

_client: httpx.AsyncClient | None = None


async def connect() -> None:
    global _client
    # Long read timeout — a streamed reply can take a while token by
    # token; connect/write stay short since those fail fast if llm-agent
    # is actually down.
    _client = httpx.AsyncClient(
        base_url=LLM_AGENT_URL,
        timeout=httpx.Timeout(120.0, connect=5.0, write=5.0),
    )


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


async def stream_chat(
    chat_id: str, message_id: str, socket_id: str, user_query: str, is_first_message: bool = False
) -> AsyncIterator[dict]:
    """Yields llm-agent's newline-delimited JSON events as they arrive —
    `{"event": "chunk"|"title_chunk", ...}` any number of times, then
    exactly one `{"event": "final", "response": {...}}`."""
    async with _client.stream(
        "POST",
        "/chat",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "socket_id": socket_id,
            "user_query": user_query,
            "is_first_message": is_first_message,
        },
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.strip():
                continue
            yield json.loads(line)
