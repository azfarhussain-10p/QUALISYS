# syntax=docker/dockerfile:1
# QUALISYS API — Python/FastAPI Production Image
# Replaces: api/Dockerfile (Node.js/Express) — Sprint Change Proposal 2026-02-20
# Story: 0-9 Docker Build Automation
# AC: 1, 4, 5, 12
# Multi-stage build — pip cache mounts for fast rebuilds
#
# Podman Compatibility:
#   OCI-compliant image, fully compatible with Podman.
#   podman build -t qualisys-api:dev ./backend
#   podman run -p 8000:8000 qualisys-api:dev
#   CI/CD pipelines use Docker on GitHub-hosted runners.

# =============================================================================
# Stage 1: Dependencies
# Install production dependencies only
# =============================================================================
FROM python:3.11-slim AS deps

WORKDIR /app

# Install system dependencies required by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 2: Builder
# Copy application source
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

COPY . .

ARG BUILD_SHA=unknown
ENV BUILD_SHA=${BUILD_SHA}

# =============================================================================
# Stage 3: Runtime
# Minimal production image
# =============================================================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Install libpq for asyncpg runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        wget \
    && rm -rf /var/lib/apt/lists/*

# Security: run as non-root user
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/sh -m appuser

# Copy installed packages and application
COPY --from=builder --chown=appuser:appgroup /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder --chown=appuser:appgroup /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder --chown=appuser:appgroup /app /app

ENV ENVIRONMENT=production
ENV PORT=8000

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
