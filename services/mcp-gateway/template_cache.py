"""In-memory template cache, keyed by resource URI. Warm after the first
tools/call that references a given template — subsequent calls skip the
resources/read round trip entirely.
"""

_cache: dict[str, str] = {}
hits = 0
misses = 0


async def get_template(uri: str, fetch) -> tuple[str, bool]:
    """Returns (html, cache_hit). `fetch` is an async no-arg callable that
    performs the actual resources/read when the URI isn't cached yet."""
    global hits, misses
    if uri in _cache:
        hits += 1
        return _cache[uri], True
    misses += 1
    html = await fetch()
    _cache[uri] = html
    return html, False
