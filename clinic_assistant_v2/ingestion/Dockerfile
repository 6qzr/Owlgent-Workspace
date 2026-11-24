
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# Copy the project dependencies
COPY pyproject.toml uv.lock ./

# Install the dependencies
RUN uv sync --frozen --no-dev

# Copy the ingestion code and PDF files
COPY ingestion ./ingestion

# Use the Python virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Run PDF ingestion once
CMD ["python", "-m", "ingestion.ingest"]
