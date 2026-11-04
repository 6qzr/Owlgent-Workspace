# Builds the API image. Used by compose locally, in CI (compose-up) and on the VM.
FROM python:3.14-slim

# uv comes from its own published image: no pip. Pinned, never `latest`: `latest` can
# point to a different uv between two builds of the same tag, so rebuilding an old tag
# for a rollback (ADR 0009) would no longer give the same image. Matches the team's uv.
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /bin/

WORKDIR /app

# Dependencies first, in their own layer. They change only when uv.lock changes,
# so editing source code does not reinstall every package.
# --frozen: fail if uv.lock is out of date, rather than silently resolving something else.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the application itself.
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# Run as a non-root user: if the app is compromised, the attacker is not root.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Put the virtualenv first on PATH so `uvicorn` is the one uv installed.
ENV PATH="/app/.venv/bin:$PATH"

# The container always listens on 8000; compose maps the published port.
EXPOSE 8000

# Docker asks the app whether it actually works, not just whether the process exists.
# start-period gives the app time to boot before a failure counts against it.
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()"

CMD ["uvicorn", "clinic_assistant.main:app", "--host", "0.0.0.0", "--port", "8000"]
