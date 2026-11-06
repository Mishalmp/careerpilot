# CareerPilot API and worker image. Build from the repository root:
#   docker build -f docker/api.Dockerfile -t careerpilot-api .
# Same image runs the API (default) and the worker (command: python -m careerpilot.cli worker).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# uv installs the exact locked dependencies (removal path: use pip with a requirements export).
RUN pip install uv

# pg_dump/pg_restore 16 for backups. They must be the same major version as the database server
# (pgvector/pgvector:pg16), and the distribution's own packages are older, so use the PostgreSQL repo.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && install -d /usr/share/keyrings \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

# The package expects the repository layout: /app/apps/api, /app/content, /app/prompts.
WORKDIR /app/apps/api
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps/api/ ./
RUN uv sync --frozen --no-dev
COPY content /app/content
COPY prompts /app/prompts

# Run as an ordinary user. The model cache and backups live in volumes owned by that user.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/.cache /app/backups \
    && chown -R app:app /app/.cache /app/backups
USER app
ENV PATH="/app/apps/api/.venv/bin:$PATH"

EXPOSE 8010
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/readyz', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "careerpilot.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8010"]
