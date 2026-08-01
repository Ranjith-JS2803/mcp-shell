"""Loads prompt text from this directory's .txt files — one flow's
prompts per file, so a future flow adds files here rather than editing
Python. Read fresh each call: cheap for a handful of small text files,
and lets a prompt be edited without restarting the service.
"""

import json
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


def load(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text()


def build_tools_block(tools: list[dict]) -> str:
    lines = []
    for entry in tools:
        fn = entry["function"]
        properties = fn.get("parameters", {}).get("properties", {})
        lines.append(f"- {fn['name']}: {fn['description']} (arguments: {json.dumps(properties)})")
    return "\n".join(lines)
