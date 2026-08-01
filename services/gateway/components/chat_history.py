"""Redis-backed snapshot writes — the frozen chat-history record for a
single artifact, keyed by snapshot_id and tagged with chat_id/msg_id so a
history view can be built later. No TTL for now: permanent until told
otherwise.
"""

import json
import os
import uuid

import redis.asyncio as redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def new_snapshot_id() -> str:
    return f"snap_{uuid.uuid4().hex[:12]}"


async def write_snapshot(
    snapshot_id: str,
    chat_id: str,
    msg_id: str,
    template_ref: str | None,
    template_html: str | None,
    structured_content: dict | None,
    meta: dict,
    created_at: str,
) -> None:
    client = get_client()
    record = {
        "snapshot_id": snapshot_id,
        "chat_id": chat_id,
        "msg_id": msg_id,
        "template_ref": template_ref,
        "template_html": template_html,
        "data_snapshot": structured_content,
        "meta": meta,
        "created_at": created_at,
    }
    await client.set(f"snapshot:{snapshot_id}", json.dumps(record))


async def read_snapshot(snapshot_id: str) -> dict | None:
    client = get_client()
    raw = await client.get(f"snapshot:{snapshot_id}")
    return json.loads(raw) if raw else None


async def ping() -> bool:
    try:
        return await get_client().ping()
    except Exception:
        return False
