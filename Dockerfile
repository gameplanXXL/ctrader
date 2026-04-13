# ctrader — multi-stage build.
#
# Stage 1: uv base image with deps synced into .venv.
# Stage 2: tailwind-build stage using the venv's `tailwindcss` binary
#          (installed by pytailwindcss during uv sync) to produce the
#          compiled CSS without Node.js.
# Stage 3: slim runtime with the venv, app source, and compiled CSS.
#
# NFR-S2: app binds to 127.0.0.1:8000 inside the container; docker-compose
# publishes it to 127.0.0.1:8000 on the host.

# ---------------------------------------------------------------------------
# Stage 1 — builder
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Install system build deps for asyncpg (compiled C extensions).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps via uv (respects uv.lock).
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 2 — tailwind build
# ---------------------------------------------------------------------------
FROM builder AS tailwind-build

WORKDIR /app

# Copy the minimum files tailwind needs to scan: templates, design
# tokens, main.css. Skip app code / tests / migrations so a trivial
# template change doesn't bust the asyncpg-install layer above.
COPY app/templates ./app/templates
COPY app/static/css ./app/static/css
COPY app/static/js ./app/static/js

# Compile Tailwind v4 via pytailwindcss (downloads the standalone binary
# on first run; cached in subsequent layers).
RUN /app/.venv/bin/tailwindcss \
        -i app/static/css/main.css \
        -o app/static/css/compiled.css \
        --minify

# ---------------------------------------------------------------------------
# Stage 3 — runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

# Runtime system deps for asyncpg.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the built venv from the builder stage.
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# App source + taxonomy + migrations.
COPY app/ ./app/
COPY taxonomy.yaml ./taxonomy.yaml
COPY migrations ./migrations

# Compiled CSS from the tailwind-build stage overwrites the placeholder
# so the runtime image always carries the minified asset.
COPY --from=tailwind-build /app/app/static/css/compiled.css /app/app/static/css/compiled.css

# Data directories (log rotation, mcp snapshots). docker-compose mounts
# these as volumes so logs survive container restarts.
RUN mkdir -p /app/data/logs /app/data/mcp-snapshots

EXPOSE 8000

# Run uvicorn directly. 0.0.0.0 inside the container is safe because
# docker-compose only publishes to 127.0.0.1 on the host.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
