"""Frontend-facing WebSocket connection management — not built yet.

Planned scope (per the merged gateway design): accept the frontend's
persistent connection per chat session, route incoming chat/pagination
messages to the right component (mcp_gateway for tool calls and resource
reads, chat_history for snapshot writes/reads), and push responses back
over the same socket.
"""
