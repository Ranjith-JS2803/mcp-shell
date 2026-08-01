"""Every LLM call goes through here and always comes back as parsed JSON —
no raw-prose path anywhere in llm-agent, per design: the model is always
instructed to answer in a fixed JSON shape, whether or not a tool is
involved.
"""

import json
import re

from openai import AsyncOpenAI

from config import LLM_API_KEY, MODEL, MODEL_BASE_URL

_client: AsyncOpenAI | None = None

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


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
        # Model didn't follow instructions — surface its raw text as the
        # reply rather than crashing the whole request.
        return {"tool_call": None, "reply": raw.strip()}


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
