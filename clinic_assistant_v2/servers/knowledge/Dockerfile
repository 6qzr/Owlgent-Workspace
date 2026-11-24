
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY servers ./servers

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8004

CMD ["python", "-m", "servers.knowledge.server"]
