
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# Copy project dependencies
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy MCP servers
COPY servers ./servers

# Use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001

# Start Appointments MCP Server
CMD ["python", "-m", "servers.appointments.server"]
