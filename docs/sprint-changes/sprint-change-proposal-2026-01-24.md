# Sprint Change Proposal: Docker to Podman Migration

**Date:** 2026-01-24
**Proposed By:** PM (John) - Product Manager
**Change Type:** Policy Compliance / Technology Migration
**Priority:** HIGH (Immediate compliance required)

---

## 1. Change Trigger

### Source
10Pearls Official Company Policy (January 2026)

### Policy Statement
> "Effective immediately, Docker Desktop should not be used on any official 10Pearls systems. Additionally, no 10Pearls email IDs should be used to register for or access Docker services. For containerization needs, we recommend using Podman as the approved alternative to Docker Desktop. Podman offers comparable functionality and aligns better with our internal security and licensing requirements."

### Compliance Requirement
- **Scope:** All 10Pearls systems (developer workstations, internal infrastructure)
- **Effective Date:** Immediate
- **Driver:** Security and licensing compliance

---

## 2. Impact Assessment

### 2.1 Affected Documents

| Document | Impact | Changes Required |
|----------|--------|------------------|
| `docs/architecture/architecture.md` | HIGH | 8 sections referencing Docker Desktop |
| `docs/stories/0-21-local-development-environment-docker-compose.md` | HIGH | Complete rewrite for Podman |
| `docs/stories/0-21-local-development-environment-docker-compose.context.xml` | HIGH | Update context XML |
| `docs/tech-specs/tech-spec-epic-0.md` | MEDIUM | 15+ Docker references |
| `docs/epics/epic-0-infrastructure.md` | MEDIUM | Story 0.21 description |
| `docs/epics/epics.md` | LOW | 2 Docker references |
| `docs/planning/prd.md` | LOW | 2 Docker references |
| `docs/planning/test-design-system.md` | LOW | 2 Docker references |
| `docs/reports/validation-report-architecture-20251211.md` | LOW | Historical reference |

### 2.2 Affected Stories

| Story ID | Title | Impact | Status |
|----------|-------|--------|--------|
| 0-9 | Docker Build Automation | MEDIUM | ready-for-dev |
| 0-21 | Local Development Environment (Docker Compose) | **CRITICAL** | ready-for-dev |
| 0-14 | Test Database Provisioning | LOW | ready-for-dev |

### 2.3 Technical Compatibility Analysis

| Component | Docker | Podman | Migration Notes |
|-----------|--------|--------|-----------------|
| Dockerfile format | Native | **Compatible** | No file changes needed |
| docker-compose.yml | Native | **Compatible** | Use `podman-compose` or `podman compose` |
| .dockerignore | Native | **Compatible** | Podman reads same format |
| OCI Images | Supported | **Supported** | Same image format |
| BuildKit | Native | Via `buildah` | Slightly different syntax |
| Volume mounts | Native | **Compatible** | Same syntax |
| Networking | docker0 | **slirp4netns** | Rootless by default |

### 2.4 Items NOT Affected

| Item | Reason |
|------|--------|
| GitHub Actions CI/CD | Runs on GitHub infrastructure, not 10Pearls systems |
| External image names (e.g., `mcr.microsoft.com/playwright`) | OCI standard, works with any runtime |
| Kubernetes deployments | Uses containerd, not Docker Desktop |
| AWS ECR | Container registry, runtime-agnostic |

---

## 3. Detailed Change Proposals

### 3.1 Architecture Document (`docs/architecture/architecture.md`)

**Current (Line 1664):**
```
| Container Runtime | Docker with minimal Alpine images | v1.0 | ...
```

**Proposed:**
```
| Container Runtime | Podman (OCI-compliant, rootless) with minimal Alpine images | v1.0 | ...
```

**Current (Line 1944):**
```
| **Docker** | 24.x | Containerization | Playwright pre-warmed pools, reproducible environments |
```

**Proposed:**
```
| **Podman** | 4.x+ | Containerization | Playwright pre-warmed pools, reproducible environments, rootless security |
```

**Current (Line 3433):**
```
| **Docker Desktop** | 24.x+ | Local containerization |
```

**Proposed:**
```
| **Podman Desktop** | 1.x+ | Local containerization (10Pearls approved) |
```

**Current (Lines 3450-3456):**
```
**2. Start Infrastructure (Docker Compose)**:
docker-compose up -d
**Docker Compose Configuration** (`docker-compose.yml`):
```

**Proposed:**
```
**2. Start Infrastructure (Podman Compose)**:
podman-compose up -d
**Compose Configuration** (`compose.yml`):
```

### 3.2 Story 0-21: Local Development Environment

**Title Change:**
- FROM: "Local Development Environment (Docker Compose)"
- TO: "Local Development Environment (Podman Compose)"

**Key Content Changes:**

| Section | Current | Proposed |
|---------|---------|----------|
| Prerequisites | Docker Desktop 4.x+ | Podman Desktop 1.x+ or Podman CLI 4.x+ |
| Download link | docker.com | podman.io / podman-desktop.io |
| Command prefix | `docker compose` | `podman-compose` or `podman compose` |
| Settings reference | Docker Desktop Settings | Podman Machine settings |
| File sharing | Docker Desktop file sharing | Podman machine volume mounts |

**Commands to Update:**

| Current | Proposed |
|---------|----------|
| `docker compose up -d` | `podman-compose up -d` |
| `docker compose down` | `podman-compose down` |
| `docker compose logs -f` | `podman-compose logs -f` |
| `docker compose exec api npm test` | `podman-compose exec api npm test` |
| `docker system prune -f` | `podman system prune -f` |
| `DOCKER_BUILDKIT=1 docker compose build` | `podman-compose build` (BuildKit not needed) |

### 3.3 Tech Spec Epic 0 (`docs/tech-specs/tech-spec-epic-0.md`)

**Line 593 - Developer Onboarding:**
- FROM: "30 min Docker Compose"
- TO: "30 min Podman Compose"

**Line 742 - Developer Training:**
- FROM: "Docker Compose demo"
- TO: "Podman Compose demo"

### 3.4 Epic 0 Infrastructure (`docs/epics/epic-0-infrastructure.md`)

**Line 695:**
- FROM: "Install Docker Desktop"
- TO: "Install Podman Desktop (or Podman CLI)"

**Story 0.21 Description:**
- FROM: "Local Development Environment (Docker Compose)"
- TO: "Local Development Environment (Podman Compose)"

### 3.5 Sprint Status YAML Updates

Update story name in `docs/sprint-status.yaml`:
- FROM: `0-21-local-development-environment-docker-compose`
- TO: `0-21-local-development-environment-podman-compose`

Rename story file:
- FROM: `docs/stories/0-21-local-development-environment-docker-compose.md`
- TO: `docs/stories/0-21-local-development-environment-podman-compose.md`

---

## 4. Migration Strategy

### 4.1 Phase 1: Documentation Updates (Immediate)
1. Update architecture.md with Podman references
2. Update tech-spec-epic-0.md
3. Update epic-0-infrastructure.md
4. Update PRD and test-design-system.md

### 4.2 Phase 2: Story Updates (Before Implementation)
1. Rename Story 0-21 file
2. Update Story 0-21 content completely
3. Regenerate Story 0-21 context XML
4. Update sprint-status.yaml

### 4.3 Phase 3: Implementation Guidance
1. Story 0-9 (Build Automation): Add note that Dockerfiles are Podman-compatible
2. Story 0-21 (Local Dev): Implement using Podman Compose
3. Add migration guide for developers already using Docker

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Developer confusion during transition | Medium | Low | Clear migration guide, team communication |
| Podman-compose compatibility issues | Low | Medium | Test all compose scenarios, document workarounds |
| BuildKit feature gaps | Low | Low | Use buildah for advanced builds if needed |
| Volume mount performance (Windows) | Medium | Medium | Document Podman machine configuration |

---

## 6. Decision Required

### Option A: Full Migration (Recommended)
- Update ALL documentation to reference Podman
- Rename Story 0-21 and update all content
- Provide developer migration guide
- **Pros:** Clean, compliant, no confusion
- **Cons:** More documentation work upfront

### Option B: Minimal Compliance
- Update only user-facing documentation (README, setup guides)
- Keep technical docs referencing "containers" generically
- **Pros:** Less work
- **Cons:** Technical debt, potential compliance gaps

### Recommendation
**Option A: Full Migration** - Given the explicit company policy and security/licensing drivers, a complete migration ensures full compliance and eliminates any ambiguity for the development team.

---

## 7. Implementation Checklist

### Immediate Actions (Today)
- [ ] Update `docs/architecture/architecture.md`
- [ ] Update `docs/tech-specs/tech-spec-epic-0.md`
- [ ] Update `docs/epics/epic-0-infrastructure.md`
- [ ] Update `docs/planning/prd.md`
- [ ] Update `docs/planning/test-design-system.md`

### Story Updates (Before Sprint)
- [ ] Rename Story 0-21 file to podman-compose
- [ ] Rewrite Story 0-21 content
- [ ] Regenerate Story 0-21 context XML
- [ ] Update sprint-status.yaml with new story name
- [ ] Add note to Story 0-9 about Podman compatibility

### Team Communication
- [ ] Notify development team of policy change
- [ ] Share Podman installation guide
- [ ] Schedule brief training/demo if needed

---

## 8. Approval

| Role | Name | Decision | Date |
|------|------|----------|------|
| Product Manager | John (PM) | Proposed | 2026-01-24 |
| Tech Lead | _______________ | _________ | _________ |
| Scrum Master | _______________ | _________ | _________ |

---

## 9. Appendix: Podman Resources

### Installation
- **Podman Desktop:** https://podman-desktop.io/
- **Podman CLI:** https://podman.io/getting-started/installation
- **Windows:** `winget install RedHat.Podman-Desktop`
- **macOS:** `brew install podman` or Podman Desktop

### Documentation
- Podman Docs: https://docs.podman.io/
- Podman-Compose: https://github.com/containers/podman-compose
- Docker to Podman Migration: https://podman.io/getting-started/

### Key Differences from Docker
1. **Rootless by default** - Enhanced security
2. **No daemon** - Podman runs without background service
3. **Systemd integration** - Native Linux service management
4. **Compatible CLI** - `alias docker=podman` works for most commands
5. **OCI compliant** - Same image format, interoperable

---

*Generated by BMad Method correct-course workflow*
*Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>*
