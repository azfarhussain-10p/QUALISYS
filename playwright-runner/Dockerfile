# syntax=docker/dockerfile:1
# Playwright Test Runner Dockerfile
# Story: 0-9 Docker Build Automation
# AC: 3, 4, 5
# Official Playwright base image with browser dependencies
#
# Podman Compatibility:
#   This Dockerfile produces OCI-compliant images and is fully compatible with
#   Podman. To build with Podman locally, replace `docker` with `podman`:
#     podman build -t playwright-runner:dev ./playwright-runner
#     podman run playwright-runner:dev
#   CI/CD pipelines use Docker on GitHub-hosted runners (not subject to
#   10Pearls workstation policy). See sprint-change-proposal-2026-01-24.md.

# =============================================================================
# Stage 1: Dependencies
# Install test dependencies on the Playwright base image
# =============================================================================
FROM mcr.microsoft.com/playwright:v1.40.0-jammy AS deps
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# =============================================================================
# Stage 2: Runner
# Copy test code and configure for headless execution
# =============================================================================
FROM mcr.microsoft.com/playwright:v1.40.0-jammy AS runner
WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Base image already includes Chromium, Firefox, and WebKit at /ms-playwright.
# Only install OS-level library dependencies (no browser re-download).
RUN npx playwright install-deps

# Runtime configuration for headless execution
ENV CI=true
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV NODE_ENV=test

# Switch to built-in non-root user (pwuser exists in Playwright base image)
USER pwuser

# Entrypoint script for flexible test execution
COPY --chown=pwuser:pwuser <<'EOF' /app/entrypoint.sh
#!/bin/bash
set -e

# Default: run all tests
# Override via: docker run playwright-runner npx playwright test --project=chromium
if [ $# -eq 0 ]; then
    exec npx playwright test
else
    exec "$@"
fi
EOF
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD []
