# Story 0.9: Docker Build Automation

Status: ready-for-dev

## Story

As a **DevOps Engineer**,
I want to **automate Docker image builds with multi-stage optimization and vulnerability scanning**,
so that **every code change produces a tested, versioned, and secure container image**.

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | Dockerfile created for API service (Node.js/Python backend) | File exists at `api/Dockerfile` |
| AC2 | Dockerfile created for Web service (Next.js frontend) | File exists at `web/Dockerfile` |
| AC3 | Dockerfile created for Playwright runner (test executor) | File exists at `playwright-runner/Dockerfile` |
| AC4 | Multi-stage builds optimize image size (build + runtime stages) | `docker images` shows optimized sizes (<500MB for API/Web) |
| AC5 | Base images use official, security-scanned versions | Dockerfiles use `node:20-alpine`, `python:3.11-slim`, or equivalent |
| AC6 | .dockerignore files exclude unnecessary files | Files exist and exclude node_modules, .git, .env, etc. |
| AC7 | Images tagged with Git SHA and branch name | `docker images` shows tags like `abc123`, `main-20260123-143022` |
| AC8 | Build time <5 minutes per service with layer caching | GitHub Actions build logs show <5 min |
| AC9 | Image vulnerability scanning integrated (Trivy) | Trivy scan runs in CI/CD and reports findings |
| AC10 | Build fails if critical/high vulnerabilities detected | CI workflow fails on HIGH/CRITICAL findings |
| AC11 | No secrets baked into images (Trivy secret scan) | Trivy secret scan passes with no findings |
| AC12 | Docker BuildKit enabled for improved caching | Dockerfiles use BuildKit syntax (`--mount=type=cache`) |

## Tasks / Subtasks

- [ ] **Task 1: API Service Dockerfile** (AC: 1, 4, 5, 12)
  - [ ] 1.1 Create `api/Dockerfile` with multi-stage build
  - [ ] 1.2 Stage 1 (builder): Install dependencies, build application
  - [ ] 1.3 Stage 2 (runtime): Copy only production artifacts
  - [ ] 1.4 Use `node:20-alpine` or `python:3.11-slim` as base
  - [ ] 1.5 Add BuildKit cache mounts for package managers
  - [ ] 1.6 Set non-root user for runtime security
  - [ ] 1.7 Add health check instruction

- [ ] **Task 2: Web Service Dockerfile** (AC: 2, 4, 5, 12)
  - [ ] 2.1 Create `web/Dockerfile` with multi-stage build
  - [ ] 2.2 Stage 1 (deps): Install dependencies
  - [ ] 2.3 Stage 2 (builder): Build Next.js application
  - [ ] 2.4 Stage 3 (runner): Copy standalone output
  - [ ] 2.5 Use `node:20-alpine` as base
  - [ ] 2.6 Configure Next.js standalone output mode
  - [ ] 2.7 Set non-root user for runtime security

- [ ] **Task 3: Playwright Runner Dockerfile** (AC: 3, 4, 5)
  - [ ] 3.1 Create `playwright-runner/Dockerfile`
  - [ ] 3.2 Use official Playwright base image or build custom
  - [ ] 3.3 Install browser dependencies (Chromium, Firefox, WebKit)
  - [ ] 3.4 Configure for headless execution
  - [ ] 3.5 Set resource limits appropriate for test execution
  - [ ] 3.6 Add test runner entrypoint script

- [ ] **Task 4: .dockerignore Configuration** (AC: 6, 11)
  - [ ] 4.1 Create `api/.dockerignore`
  - [ ] 4.2 Create `web/.dockerignore`
  - [ ] 4.3 Create `playwright-runner/.dockerignore`
  - [ ] 4.4 Exclude: node_modules, .git, .env*, *.log, coverage/, dist/
  - [ ] 4.5 Exclude: .env.local, .env.*.local, secrets/, credentials/

- [ ] **Task 5: Image Tagging Strategy** (AC: 7)
  - [ ] 5.1 Implement Git SHA tagging in CI/CD workflow
  - [ ] 5.2 Implement branch-timestamp tagging
  - [ ] 5.3 Implement `latest` tag for main branch (dev only)
  - [ ] 5.4 Implement `production-vX.Y.Z` semantic versioning
  - [ ] 5.5 Document tagging strategy in README

- [ ] **Task 6: Vulnerability Scanning** (AC: 9, 10, 11)
  - [ ] 6.1 Add Trivy scan step to reusable-build workflow
  - [ ] 6.2 Configure severity threshold: fail on HIGH, CRITICAL
  - [ ] 6.3 Add Trivy secret scanning for baked-in secrets
  - [ ] 6.4 Configure scan output format (table + SARIF for GitHub)
  - [ ] 6.5 Upload SARIF results to GitHub Security tab
  - [ ] 6.6 Document vulnerability remediation process

- [ ] **Task 7: Build Optimization & Validation** (AC: 8, 12, All)
  - [ ] 7.1 Enable Docker BuildKit in CI/CD (DOCKER_BUILDKIT=1)
  - [ ] 7.2 Configure GitHub Actions cache for Docker layers
  - [ ] 7.3 Measure and optimize build times (<5 min target)
  - [ ] 7.4 Test builds locally with `docker build`
  - [ ] 7.5 Test builds in CI/CD with sample PR
  - [ ] 7.6 Verify image sizes meet targets
  - [ ] 7.7 Document build process in CONTRIBUTING.md

## Dev Notes

### Architecture Alignment

This story implements Docker build automation per the architecture document:

- **Optimized Images**: Multi-stage builds reduce image size and attack surface
- **Security Scanning**: Trivy catches vulnerabilities before deployment
- **Reproducible Builds**: Git SHA tagging ensures exact version traceability
- **CI/CD Integration**: Builds automated via GitHub Actions (Story 0.8)

### Technical Constraints

- **Base Images**: Only official, regularly-updated base images
- **Non-Root User**: All containers run as non-root for security
- **No Secrets**: Never bake secrets into images (runtime injection only)
- **Build Time**: <5 minutes per service with caching
- **Image Size**: <500MB for API/Web, <2GB for Playwright (browsers)

### Multi-Stage Build Pattern

```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
RUN npm run build

# Stage 2: Runtime
FROM node:20-alpine AS runner
WORKDIR /app
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules
USER nodejs
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s CMD wget -q --spider http://localhost:3000/health || exit 1
CMD ["node", "dist/main.js"]
```

### Image Size Targets

| Service | Base Image | Target Size | Rationale |
|---------|------------|-------------|-----------|
| qualisys-api | node:20-alpine | <200MB | Minimal Node.js runtime |
| qualisys-web | node:20-alpine | <300MB | Next.js standalone output |
| playwright-runner | mcr.microsoft.com/playwright | <2GB | Includes browsers |

### Image Tagging Strategy

| Tag Pattern | When Applied | Example | Purpose |
|-------------|--------------|---------|---------|
| `{git-sha}` | Every build | `a1b2c3d` | Immutable reference |
| `{branch}-{timestamp}` | Every build | `main-20260123-143022` | Branch tracking |
| `latest` | Main branch only | `latest` | Dev convenience |
| `staging-{date}` | Staging deploy | `staging-20260123` | Environment tracking |
| `production-v{X.Y.Z}` | Release | `production-v1.2.3` | Semantic version |

### Trivy Scanning Configuration

```yaml
# In reusable-build.yml
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: '${{ env.ECR_REGISTRY }}/${{ inputs.service_name }}:${{ github.sha }}'
    format: 'sarif'
    output: 'trivy-results.sarif'
    severity: 'HIGH,CRITICAL'
    exit-code: '1'  # Fail on HIGH/CRITICAL

- name: Run Trivy secret scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: '${{ env.ECR_REGISTRY }}/${{ inputs.service_name }}:${{ github.sha }}'
    scan-type: 'secret'
    exit-code: '1'  # Fail if secrets found

- name: Upload Trivy scan results
  uses: github/codeql-action/upload-sarif@v2
  with:
    sarif_file: 'trivy-results.sarif'
```

### .dockerignore Template

```
# Dependencies
node_modules/
.pnp
.pnp.js

# Build outputs
dist/
build/
.next/
out/

# Environment and secrets
.env
.env.*
.env.local
*.pem
secrets/
credentials/

# Git
.git/
.gitignore

# IDE
.idea/
.vscode/
*.swp
*.swo

# Logs
*.log
npm-debug.log*
yarn-debug.log*

# Test
coverage/
.nyc_output/
test-results/

# Docker
Dockerfile*
docker-compose*
.dockerignore
```

### Project Structure Notes

```
/
├── api/
│   ├── Dockerfile           # API service multi-stage build
│   ├── .dockerignore        # API exclusions
│   └── src/
├── web/
│   ├── Dockerfile           # Web service multi-stage build
│   ├── .dockerignore        # Web exclusions
│   └── src/
├── playwright-runner/
│   ├── Dockerfile           # Playwright test runner
│   ├── .dockerignore        # Playwright exclusions
│   └── tests/
├── .github/
│   └── workflows/
│       └── reusable-build.yml  # Updated with Trivy scanning
└── docs/
    └── docker-build-guide.md   # Build documentation
```

### Dependencies

- **Story 0.6** (Container Registry) - REQUIRED: ECR repositories for image push
- **Story 0.8** (GitHub Actions) - REQUIRED: reusable-build.yml workflow
- Outputs used by subsequent stories:
  - Story 0.10 (Automated Tests): Playwright runner image
  - Story 0.11 (Staging Deployment): API and Web images
  - Story 0.12 (Production Deployment): Production-tagged images

### Security Considerations

From Red Team Analysis:

1. **Threat: Vulnerable dependencies** → Mitigated by Trivy scanning (AC9, AC10)
2. **Threat: Secrets in images** → Mitigated by Trivy secret scan (AC11)
3. **Threat: Root container escape** → Mitigated by non-root user
4. **Threat: Large attack surface** → Mitigated by multi-stage builds (AC4)
5. **Threat: Outdated base images** → Mitigated by Dependabot updates

### Build Performance Optimization

| Technique | Benefit | Implementation |
|-----------|---------|----------------|
| Multi-stage builds | Smaller images, faster pulls | Separate build and runtime stages |
| BuildKit cache mounts | Faster dependency install | `--mount=type=cache` for npm/pip |
| GitHub Actions cache | Faster CI builds | `actions/cache` for Docker layers |
| Layer ordering | Better cache utilization | COPY package*.json before COPY . |
| .dockerignore | Smaller build context | Exclude node_modules, .git |

### References

- [Source: docs/tech-specs/tech-spec-epic-0.md#Docker-Build-Automation]
- [Source: docs/tech-specs/tech-spec-epic-0.md#Security-Threat-Model]
- [Source: docs/epics/epic-0-infrastructure.md#Story-0.9]
- [Source: docs/architecture/architecture.md#Container-Architecture]

## Dev Agent Record

### Context Reference

- [docs/stories/0-9-docker-build-automation.context.xml](./0-9-docker-build-automation.context.xml)

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

### File List

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-01-23 | SM Agent (Bob) | Story drafted from Epic 0 tech spec and epic file |
| 2026-01-23 | SM Agent (Bob) | Context XML generated, status: drafted → ready-for-dev |
