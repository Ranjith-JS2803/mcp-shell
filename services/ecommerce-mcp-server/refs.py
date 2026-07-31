"""Stateless data_source_ref helpers.

A data_source_ref is a self-sufficient string of the form
`tool_name?param1=value1&param2=value2` that encodes everything needed to
replay a tool call — no session state, so the gateway can reconstruct the
exact MCP call for pagination or drill-down, even days later from history.
"""

from urllib.parse import parse_qsl, quote, urlencode


def build_ref(tool_name: str, **params) -> str:
    clean = {k: v for k, v in params.items() if v is not None}
    if not clean:
        return tool_name
    return f"{tool_name}?{urlencode(clean)}"


def parse_ref(ref: str) -> tuple[str, dict[str, str]]:
    tool_name, _, query = ref.partition("?")
    params = dict(parse_qsl(query))
    return tool_name, params


def data_resource_uri(ref: str) -> str:
    """The data_source_ref contains literal `?`/`&`/`=`, so it must be
    percent-encoded before being embedded as the {ref} segment of the
    data://{ref} resource template — otherwise those chars get parsed as
    URI template structure instead of matched as the variable's value."""
    return f"data://{quote(ref, safe='')}"
