"""Two kinds of LLM call: `ask_json` for control-flow decisions (always
forced JSON, fully parsed before acting on it — the tool-routing choice),
and `stream_text` for anything user-facing (plain text, streamed token by
token — forcing JSON there would mean streaming unreadable partial JSON
to the user instead of readable text).
"""

import json
import re
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from config import LLM_API_KEY, MODEL, MODEL_BASE_URL

_client: AsyncOpenAI | None = None

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=MODEL_BASE_URL, api_key=LLM_API_KEY)
    return _client


def _parse_json(raw: str) -> dict:
    cleaned = _FENCE_RE.sub("", raw.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Model didn't follow instructions — treat it as "no tool" rather
        # than crashing the whole request.
        return {"tool_call": None}


async def ask_json(system_prompt: str, user_query: str) -> dict:
    client = get_client()
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
        response_format={"type": "json_object"},
    )
    return _parse_json(response.choices[0].message.content or "")


async def _strip_thinking(chunks: AsyncIterator[str]) -> AsyncIterator[str]:
    """Some reasoning models prepend a <think>...</think> scratchpad
    before the real answer, even when told to just answer directly. That
    block is internal monologue, not a reply — drop it rather than
    streaming (and persisting) it as the user-facing text. Buffers only
    while it's still ambiguous whether a <think> block is starting or
    whether one is still open; once resolved either way, tokens pass
    through immediately, so streaming latency for the real answer is
    unaffected.
    """
    buffer = ""
    in_think: bool | None = None  # None = undecided yet
    trimming_ws = False  # true right after </think>, until real content starts

    async for piece in chunks:
        if trimming_ws:
            piece = piece.lstrip()
            if not piece:
                continue
            trimming_ws = False

        if in_think is False:
            yield piece
            continue

        buffer += piece

        if in_think is None:
            stripped = buffer.lstrip()
            if stripped.startswith(THINK_OPEN):
                in_think = True
                buffer = stripped[len(THINK_OPEN) :]
            elif len(stripped) >= len(THINK_OPEN):
                in_think = False
                yield buffer
                buffer = ""
            continue  # still undecided — keep buffering

        idx = buffer.find(THINK_CLOSE)
        if idx != -1:
            in_think = False
            trimming_ws = True
            remainder = buffer[idx + len(THINK_CLOSE) :].lstrip()
            buffer = ""
            if remainder:
                trimming_ws = False
                yield remainder
        # else: still inside the think block — keep discarding into buffer

    if in_think is None and buffer:
        yield buffer  # stream ended before we ever resolved — flush what we have


async def stream_text(system_prompt: str, user_query: str) -> AsyncIterator[str]:
    client = get_client()
    stream = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
        stream=True,
    )

    async def raw_pieces():
        async for chunk in stream:
            piece = chunk.choices[0].delta.content if chunk.choices else None
            if piece:
                yield piece

    async for piece in _strip_thinking(raw_pieces()):
        yield piece
