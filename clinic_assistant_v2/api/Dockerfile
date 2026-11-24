FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# Install the locked dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY api ./api

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
