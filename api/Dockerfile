# syntax=docker/dockerfile:1
# API Service Dockerfile
# Story: 0-9 Docker Build Automation
# AC: 1, 4, 5, 12
# Multi-stage build with BuildKit cache mounts
#
# Podman Compatibility:
#   This Dockerfile produces OCI-compliant images and is fully compatible with
#   Podman. To build with Podman locally, replace `docker` with `podman`:
#     podman build -t qualisys-api:dev ./api
#     podman run -p 3000:3000 qualisys-api:dev
#   CI/CD pipelines use Docker on GitHub-hosted runners (not subject to
#   10Pearls workstation policy). See sprint-change-proposal-2026-01-24.md.

# =============================================================================
# Stage 1: Dependencies
# Install only production + dev dependencies for building
# =============================================================================
FROM node:20-alpine AS deps
WORKDIR /app

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# =============================================================================
# Stage 2: Builder
# Build the application from source
# =============================================================================
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG BUILD_SHA=unknown
ENV BUILD_SHA=${BUILD_SHA}

RUN npm run build

# Prune dev dependencies for production
RUN --mount=type=cache,target=/root/.npm \
    npm ci --omit=dev && \
    npm cache clean --force

# =============================================================================
# Stage 3: Runtime
# Minimal production image with only built artifacts
# =============================================================================
FROM node:20-alpine AS runner
WORKDIR /app

# Security: run as non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S appuser -u 1001 -G nodejs

# Copy production artifacts
COPY --from=builder --chown=appuser:nodejs /app/dist ./dist
COPY --from=builder --chown=appuser:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=appuser:nodejs /app/package.json ./package.json

# Runtime configuration
ENV NODE_ENV=production
ENV PORT=3000

# Switch to non-root user
USER appuser

EXPOSE 3000

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:3000/api/health || exit 1

CMD ["node", "dist/main.js"]
