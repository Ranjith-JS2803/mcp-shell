"""Enforces the PRD's payload size guard on structuredContent: a careless
tool could return thousands of raw rows — this is where that gets caught
before it reaches the LLM context or the snapshot store, not in the MCP
server itself.
"""

import json

MAX_ITEMS = 500
MAX_BYTES = 256 * 1024


class PayloadTooLarge(Exception):
    def __init__(self, payload_bytes: int) -> None:
        self.payload_bytes = payload_bytes
        super().__init__(f"structuredContent is {payload_bytes} bytes, exceeds {MAX_BYTES}")


def apply_size_guard(structured_content: dict | None) -> tuple[dict | None, dict]:
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
