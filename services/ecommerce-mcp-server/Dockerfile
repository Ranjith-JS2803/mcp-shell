# ecommerce-mcp-server — SQLite-backed MCP JSON-RPC server, seed data, templates
# Build context is the repo root (see docker-compose.yml) so this can
# install from the shared root pyproject.toml / uv.lock.
FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY services/ecommerce-mcp-server/ ./

ENV DB_PATH=/app/data/mcp_server.db
EXPOSE 8002

CMD ["uv", "run", "python", "main.py"]
