# llm-agent — tool discovery + LLM calls
# Build context is the repo root (see docker-compose.yml) so this can
# install from the shared root pyproject.toml / uv.lock.
FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY services/llm-agent/ ./

EXPOSE 8004

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
