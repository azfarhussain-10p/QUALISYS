# syntax=docker/dockerfile:1
# Web Service Dockerfile (Next.js)
# Story: 0-9 Docker Build Automation
# AC: 2, 4, 5, 12
# Multi-stage build with Next.js standalone output
#
# Podman Compatibility:
#   This Dockerfile produces OCI-compliant images and is fully compatible with
#   Podman. To build with Podman locally, replace `docker` with `podman`:
#     podman build -t qualisys-web:dev ./web
#     podman run -p 3000:3000 qualisys-web:dev
#   CI/CD pipelines use Docker on GitHub-hosted runners (not subject to
#   10Pearls workstation policy). See sprint-change-proposal-2026-01-24.md.

# =============================================================================
# Stage 1: Dependencies
# Install all dependencies (including devDependencies for build)
# =============================================================================
FROM node:20-alpine AS deps
WORKDIR /app

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# =============================================================================
# Stage 2: Builder
# Build the Next.js application with standalone output
# =============================================================================
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG BUILD_SHA=unknown
ENV BUILD_SHA=${BUILD_SHA}
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# =============================================================================
# Stage 3: Runner
# Minimal production image with Next.js standalone output
# =============================================================================
FROM node:20-alpine AS runner
WORKDIR /app

# Security: run as non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001 -G nodejs

# Runtime configuration
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Copy public assets (not included in standalone output)
COPY --from=builder /app/public ./public

# Copy standalone output (includes server.js and required node_modules)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Switch to non-root user
USER nextjs

EXPOSE 3000

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD wget -q --spider http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]
