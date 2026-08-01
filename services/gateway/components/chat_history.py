"""Redis JSON chat-history — one document per (chat_id, message_id),
holding the user's query, the assistant's reply, and any artifact
produced by a tool call, all in one place. There is no separate snapshot
store: an artifact is just a field on the message it belongs to, and
chat_id + message_id (already known to every caller) is the only address
needed to fetch it back.
"""

import os
from datetime import datetime, timezone

import redis.asyncio as redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def _key(chat_id: str, message_id: str) -> str:
    return f"chat-history:{chat_id}:{message_id}"


def _index_key(chat_id: str) -> str:
    return f"chat-history-index:{chat_id}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_message(chat_id: str, message_id: str, user_query: str) -> dict:
    """Called the moment a user query comes in — creates the document that
    the reply and (if any) the artifact get merged into as they arrive."""
    client = get_client()
    now = _now()
    doc = {
        "chat_id": chat_id,
        "message_id": message_id,
        "user_query": user_query,
        "reply": None,
        "artifact": None,
        "created_at": now,
        "updated_at": now,
    }
    await client.json().set(_key(chat_id, message_id), "$", doc)
    await client.zadd(_index_key(chat_id), {message_id: datetime.now(timezone.utc).timestamp()})
    return doc


async def update_reply(chat_id: str, message_id: str, reply: str) -> None:
    client = get_client()
    key = _key(chat_id, message_id)
    await client.json().set(key, "$.reply", reply)
    await client.json().set(key, "$.updated_at", _now())


async def update_artifact(chat_id: str, message_id: str, artifact: dict) -> None:
    client = get_client()
    key = _key(chat_id, message_id)
    await client.json().set(key, "$.artifact", artifact)
    await client.json().set(key, "$.updated_at", _now())


async def get_message(chat_id: str, message_id: str) -> dict | None:
    client = get_client()
    return await client.json().get(_key(chat_id, message_id))


async def get_chat_history(chat_id: str) -> list[dict]:
    """Ordered by created_at (the zset score) — oldest first."""
    client = get_client()
    message_ids = await client.zrange(_index_key(chat_id), 0, -1)
    if not message_ids:
        return []
    raw = await client.json().mget([_key(chat_id, mid) for mid in message_ids], "$")
    # RedisJSON's MGET wraps each key's result in its own array (JSONPath
    # can match multiple nodes per key) — flatten the one-doc-per-key case.
    docs = []
    for entry in raw:
        if isinstance(entry, list):
            docs.extend(entry)
        elif entry is not None:
            docs.append(entry)
    return docs


async def ping() -> bool:
    try:
        return await get_client().ping()
    except Exception:
        return False
