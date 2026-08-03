# mcp-shell

**Have you ever wondered how Claude or ChatGPT render a chart or a data table inside the
chat interface — without freezing the UI, without the entire dataset living in the model's
context, and without the artifact breaking when you scroll back through history days later?**

`mcp-shell` is an open-source reference implementation that answers that question end-to-end,
on a real 50,000-row e-commerce dataset, using nothing but the Model Context Protocol, a small
FastAPI gateway, Redis, and a sandboxed iframe.

## The problem

The naive way to build an MCP-connected chat product is to let a tool dump everything into its
response: raw rows, rendered HTML, the whole dataset. That response bloats the LLM's context
window, slows the frontend, and quietly rots — six months later nobody remembers why chat history
shows different numbers than the database, because history was never actually *frozen*, it was
just re-rendered from live data every time.

The root cause is always the same: there is no separation between *what to render* and *the data
being rendered*. Fix that one architectural seam, and every one of those problems disappears at
once. That's the entire premise of this project.

## The fix, in four moves

1. **Tools never return raw rows.** Every MCP tool returns a `resource_link` — a pointer to a
   template — plus a handful of aggregated numbers. A tool answering "revenue by region" returns
   six totals, not fifty thousand orders.
2. **Templates are real MCP resources, not files the gateway happens to know about.** The chart,
   the table, and the PDF viewer are each fetched via `resources/read`, cached once, and rendered
   inside a sandboxed `<iframe sandbox="allow-scripts">` — no live server, no network access, no
   trust placed in the HTML beyond what the sandbox allows.
3. **Pagination carries no session state.** Loading page two of a table, or the next chunk of a
   report, means resolving a `next_ref` string the server handed back — the same ref works whether
   it's replayed one second or three days later, because there's nothing server-side to expire.
4. **Chat history is a fact, not a query.** Every turn is a single RedisJSON document —
   `chat-history:<chat_id>:<message_id>` — holding the question, the answer, and the artifact that
   was shown, frozen at the moment it was created. Scrolling back never re-runs a tool; it reads
   what actually happened.

## What it looks like end-to-end

A user asks "show me revenue by region." That query goes to `gateway`, which drops an
immediate acknowledgment back over HTTP and hands the real work to `llm-agent` in the
background. `llm-agent` calls Groq, decides `revenue_chart` is the right tool, and asks
`gateway` to run it. `gateway` calls the MCP server, gets back six numbers and a link to a
chart template, caches the template, and writes the whole turn to Redis. `llm-agent` writes
one sentence of framing back through `gateway`, and the finished answer — chart, data, and
text — arrives at the frontend over a WebSocket it opened when the page loaded. The user never
watched a spinner wait on an HTTP response; the answer just showed up.

If the MCP server is down, or the LLM call fails, or the WebSocket listener has disconnected —
none of that leaves the user stuck. Every layer degrades to a plain-language fallback, and the
history record is always written, even when the answer is "something went wrong." Nothing about
this system assumes the happy path.

## Why this is worth your time as a recruiter or engineer skimming a repo

This isn't a toy chatbot demo. It's five independently-deployable services — an MCP server, a
gateway, an LLM agent, Redis, and a React frontend — each with a single clear job, talking to
each other over real protocols (JSON-RPC for MCP, REST for orchestration, WebSocket for
delivery), with failure handling that was actually exercised by killing services mid-request and
watching the system recover, not assumed to work. It's the same architectural pattern that
production chat products use to keep rich UI out of an LLM's context — built from scratch,
documented as it was built, and runnable with one command.
