# gateway — template cache, payload size guard, snapshot writes, pagination
# Build context is the repo root (see docker-compose.yml) so this can
# install from the shared root pyproject.toml / uv.lock.
FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY services/gateway/ ./

EXPOSE 8003

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
