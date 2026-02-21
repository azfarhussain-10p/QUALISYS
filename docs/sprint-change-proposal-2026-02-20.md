# Sprint Change Proposal — Backend Tech Stack Correction

| Attribute | Detail |
|-----------|--------|
| **Date** | 2026-02-20 |
| **Raised By** | DEV Agent (Amelia) — pre-implementation discovery |
| **Documented By** | SM Agent (Bob) — correct-course workflow |
| **Change Scope** | Minor — infrastructure scaffold only |
| **MVP Impact** | None |
| **Status** | Approved — 2026-02-20 |

---

## Section 1: Issue Summary

### Problem Statement

During Epic 0 Story 0-11 (Staging Auto-Deployment), the DEV agent created `api/src/health.ts` using TypeScript/Express to satisfy Kubernetes health probe acceptance criteria. This single file established the `api/` directory as a TypeScript/Node.js service — silently contradicting the Architecture document and Tech Spec which specify Python 3.11+/FastAPI as the backend framework throughout.

The divergence propagated across Epic 0 as subsequent infrastructure stories added `api/src/logger/index.ts` and `api/src/metrics/prometheus.ts` — both TypeScript — without triggering review flags.

### Discovery Context

- **When:** Start of Epic 1, Story 1.1 (User Account Creation) — pre-implementation phase
- **Who:** DEV agent (Amelia) during Step 0.5 (discover inputs / codebase scan)
- **How:** DEV agent detected `api/src/health.ts` (Express, TypeScript) and halted before writing any business logic, correctly flagging the conflict
- **Impact at Discovery:** Zero business logic committed in wrong language — correction cost is minimal

### Evidence

| File | Problem |
|------|---------|
| `api/src/health.ts` | TypeScript/Express health routes — should be Python/FastAPI |
| `api/src/logger/index.ts` | TypeScript logger — should be Python `logging` + JSON formatter |
| `api/src/metrics/prometheus.ts` | TypeScript Prometheus metrics — should be `prometheus-fastapi-instrumentator` |
| `api/Dockerfile` | Node.js base image — should be Python 3.11 slim |
| `api/Containerfile.dev` | Node.js dev container — should be Python 3.11 dev image |
| `compose.yml` | `api` service configured for Node.js/TypeScript — should use Python/uvicorn entrypoint |

### Artefacts Confirmed Correct (No Changes Required)

| File | Status |
|------|--------|
| `docs/architecture/architecture.md` | ✅ Specifies Python/FastAPI throughout — never wrong |
| `docs/tech-specs/tech-spec-epic-1.md` | ✅ Specifies Python paths and packages — never wrong |
| All 13 Epic 1 story files | ✅ Reference `backend/services/*.py`, `pytest`, `passlib` — already aligned |
| `tests/conftest.py` | ✅ Python/pytest — correct |
| `tests/integration/tenant-isolation.test.ts` | ✅ DB-level TypeScript tests — framework-agnostic, keep as-is |
| `factories/*.ts` | ✅ TypeScript test data factories — keep as-is |

---

## Section 2: Impact Analysis

### Epic Impact

| Epic | Impact |
|------|--------|
| Epic 0 — Infrastructure | Minor: 6 scaffold files require recreation in Python |
| Epic 1 — Foundation & Administration | Zero: all 13 stories already reference Python paths |
| Epic 2 — AI Agent Platform | Zero: Python/AI/ML ecosystem — benefits from correction |
| Epic 3 — Manual Testing | Zero |
| Epic 4 — Automated Execution & Self-Healing | Zero: self-healing ML requires Python |
| Epic 5 — Dashboards & Ecosystem Integration | Zero |
| Epic 6 — Advanced Agents | Zero: LLM customization — Python-native |
| Epic 7 — Agent Skills Integration | Zero: LangChain bridge explicitly Python |

### Story Impact

- **Current sprint (Epic 1):** Zero story changes — all 13 stories proceed as written
- **Future sprints:** Zero story changes — all stories already aligned with Python

### Technical Impact

- 6 files require recreation (health, logger, metrics, 2 Dockerfiles, compose.yml)
- No business logic involved — scaffold/infrastructure only
- No database schema changes
- No API contract changes
- No frontend changes

---

## Section 3: Recommended Approach

### Option 1: Direct Adjustment ✅ SELECTED

Recreate 6 TypeScript/Node.js scaffold files with Python/FastAPI equivalents.

- **Effort:** Low — direct 1:1 translation, no novel patterns
- **Risk:** Low — Python equivalents are well-established in the tech spec
- **Timeline impact:** Negligible — unblocks Story 1.1 immediately

### Option 2: Rollback — Not Applicable

Nothing to roll back to. TypeScript was never the intended state. This is a correction to restore the original design intent.

### Option 3: MVP Review — Not Applicable

MVP scope is unaffected. This is an infrastructure scaffold fix only.

### Rationale for Option 1

1. **Lowest cost:** 6 files with no business logic — minimal rework
2. **Restores design intent:** Architecture and Tech Spec were always correct; this fix aligns the implementation to them
3. **Eliminates long-term friction:** Epics 2, 4, 6, 7 rely heavily on the Python AI/ML ecosystem (LangChain, HuggingFace, vector DBs, scikit-learn). TypeScript would impose significant ecosystem disadvantages across 50+ future stories
4. **No team disruption:** Epic 1 stories are unchanged; sprint momentum is preserved

---

## Section 4: Detailed Change Proposals

### Change 1: `api/src/health.ts` → `backend/src/health.py`

**OLD:** TypeScript/Express health and readiness routes
```typescript
import type { Express } from 'express';
export function registerHealthRoutes(app: Express, deps?) { ... }
```

**NEW:** FastAPI router with equivalent liveness and readiness endpoints
```python
# backend/src/health.py
from fastapi import APIRouter, status
router = APIRouter()

@router.get("/health")
async def liveness(): ...

@router.get("/ready")
async def readiness(): ...
```

**Rationale:** Direct functional equivalent. Same endpoints, same HTTP semantics, Python/FastAPI.

---

### Change 2: `api/src/logger/index.ts` → `backend/src/logger.py`

**OLD:** TypeScript Pino structured JSON logger
**NEW:** Python `logging` with JSON formatter (structlog or python-json-logger), matching Epic 0 Story 0-20 Pino field conventions (`trace_id`, `tenant_id`, `request_id`)

**Rationale:** Maintains same structured log schema; integrates with Fluent Bit DaemonSet from Story 0-20.

---

### Change 3: `api/src/metrics/prometheus.ts` → `backend/src/metrics.py`

**OLD:** TypeScript Prometheus metrics module
**NEW:** `prometheus-fastapi-instrumentator` (already listed in tech-spec-epic-1.md §7 dependencies)

**Rationale:** Direct replacement; package already specified in Tech Spec.

---

### Change 4: `api/Dockerfile` → Python 3.11 slim base image

**OLD:** Node.js base image
**NEW:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Rationale:** Matches architecture spec; uvicorn is the ASGI server specified in tech-spec-epic-1.md §7.

---

### Change 5: `api/Containerfile.dev` → Python 3.11 dev image

**OLD:** Node.js dev container
**NEW:** Python 3.11 dev container with `--reload` flag for hot-reload development

**Rationale:** Maintains dev workflow parity; matches compose.yml local development setup from Story 0-21.

---

### Change 6: `compose.yml` — Update `api` service

**OLD:** `api` service using Node.js/TypeScript entrypoint
**NEW:** `api` service using `uvicorn src.main:app --reload --host 0.0.0.0 --port 8000`

**Rationale:** Aligns local development environment with Python/FastAPI service definition.

---

## Section 5: Implementation Handoff

### Scope Classification: **Minor**

Infrastructure scaffold recreation only. No business logic, no API contract changes, no story modifications.

### Handoff Plan

| Agent | Action | Priority |
|-------|--------|----------|
| **DEV Agent (Amelia)** | Recreate `backend/src/health.py` | 1st |
| **DEV Agent (Amelia)** | Recreate `backend/src/logger.py` | 2nd |
| **DEV Agent (Amelia)** | Recreate `backend/src/metrics.py` | 3rd |
| **DEV Agent (Amelia)** | Recreate `api/Dockerfile` (Python 3.11 slim) | 4th |
| **DEV Agent (Amelia)** | Recreate `api/Containerfile.dev` (Python 3.11 dev) | 5th |
| **DEV Agent (Amelia)** | Update `compose.yml` api service entrypoint | 6th |
| **SM Agent (Bob)** | Update `sprint-status.yaml` changelog | 7th |
| **DEV Agent (Amelia)** | Resume Story 1.1 implementation in Python/FastAPI | 8th |

### Success Criteria

- [ ] All 6 TypeScript/Node.js scaffold files replaced with Python equivalents
- [ ] `compose.yml` `api` service starts successfully with Python/uvicorn
- [ ] `/health` and `/ready` endpoints return correct responses
- [ ] `sprint-status.yaml` changelog updated with correction note
- [ ] Story 1.1 implementation proceeds in Python/FastAPI without further blockers

### PM/Architect Action Required

**None.** Architecture and Tech Spec were correct throughout. No document updates required from PM or Architect.

---

## Changelog

| Date | Action | By |
|------|--------|-----|
| 2026-02-20 | Sprint Change Proposal created | SM Agent (Bob) |
