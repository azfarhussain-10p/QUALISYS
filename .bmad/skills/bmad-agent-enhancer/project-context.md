# QUALISYS — Project Context

Reference for agents that need codebase awareness and QUALISYS-specific conventions.

## Product Overview

**QUALISYS** is an **AI System Quality Assurance Platform** (SaaS B2B) built on the Enterprise BMad Method track. It uses **7 specialized AI agents** to transform software testing from a manual bottleneck into an intelligent, self-maintaining system. The platform covers the full testing lifecycle: requirements ingestion, test generation, automated execution, self-healing maintenance, and executive dashboards.

**"5-Minute Value Moment":** Upload a PRD, connect app URL + GitHub repo, select agents — receive complete test suites (manual checklists, Playwright scripts, BDD scenarios, coverage matrices) in under 5 minutes.

## Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Frontend** | Vite + React 18 + TypeScript + Tailwind CSS + shadcn/ui | Component-driven SPA with design system |
| **Backend** | Python 3.11+ FastAPI + SQLAlchemy 2.x | Async-first API with production ORM |
| **AI Orchestration** | LangChain (MVP) + Custom Orchestrator (Production) | `litellm` wrapper in `backend/src/patterns/llm_pattern.py` |
| **LLM Providers** | OpenAI GPT-4 (MVP), Claude API (Agent Skills), Self-hosted vLLM (Post-MVP) | Multi-provider strategy, no vendor lock-in |
| **Database** | PostgreSQL 15+ with pgvector | Multi-tenant schemas (schema-per-tenant), vector search, RLS |
| **Cache** | Redis 7+ (cluster mode) | Sessions, rate limiting, LLM response caching, circuit breakers |
| **Browser Automation** | Playwright | Cross-browser testing, smart locators, DOM crawling, self-healing support |
| **Container Runtime** | Podman + Kubernetes (EKS / AKS) | Enterprise container orchestration with HPA autoscaling |
| **Observability** | OpenTelemetry + LangFuse + Prometheus + Grafana | Full-stack observability including LLM cost tracking |
| **Infrastructure** | Terraform + Helm + GitHub Actions | Infrastructure as Code with multi-cloud support (AWS + Azure) |
| **Migrations** | Alembic | Sequential numbering: `{NNN}_{description}.py` |
| **Auth** | JWT (RS256), TOTP 2FA, Argon2id, OAuth 2.0 (Google), SAML 2.0 (Post-MVP) | 6-role RBAC enforced at API level |
| **Testing** | pytest (unit, integration, security, pattern) | All tests must pass 100% before story moves to review |
| **Object Storage** | S3 / Azure Blob Storage | Artifacts, evidence, exports |

### Multi-Cloud Architecture (AWS + Azure)

A single `CLOUD_PROVIDER` variable switches the entire deployment:

| Component | AWS | Azure |
|-----------|-----|-------|
| Kubernetes | EKS | AKS |
| Database | RDS PostgreSQL | PostgreSQL Flexible Server |
| Cache | ElastiCache Redis | Azure Cache for Redis |
| Container Registry | ECR | ACR |
| Secrets | Secrets Manager | Key Vault |
| Object Storage | S3 | Blob Storage |
| Monitoring | CloudWatch + CloudTrail | Log Analytics + Activity Log |

## QUALISYS AI Agents

### MVP Agents (Epic 2)

| Agent | Service File | Mission |
|-------|-------------|---------|
| **BAConsultant** | `backend/src/services/agents/ba_consultant.py` | Analyze requirements, detect gaps, generate test-ready user stories |
| **QAConsultant** | `backend/src/services/agents/qa_consultant.py` | Create test strategies, manual checklists, BDD/Gherkin scenarios |
| **AutomationConsultant** | `backend/src/services/agents/automation_consultant.py` | Generate Playwright scripts with smart locators, DOM crawling |

### Post-MVP Agents (Epic 6)

AI Log Reader, Security Scanner Orchestrator, Performance/Load Agent, DatabaseConsultant.

### Agent Pipeline

Orchestrated by `backend/src/services/agents/orchestrator.py`:
- Input sources: Documents (PDF/Word/MD), GitHub repos (read-only), Live app URLs (DOM crawling)
- Pipeline: BAConsultant → QAConsultant → AutomationConsultant
- All vector embeddings stored in pgvector for cross-agent retrieval

## Directory Layout

```
QUALISYS/
├── backend/
│   ├── alembic/versions/         # DB migrations (numbered: 001_, 002_, ...)
│   ├── src/
│   │   ├── api/
│   │   │   └── v1/               # API domain routers
│   │   │       ├── auth/          # Login, MFA, sessions
│   │   │       ├── users/         # User profiles
│   │   │       ├── orgs/          # Organizations, export
│   │   │       ├── projects/      # Projects, members
│   │   │       ├── members/       # Team members
│   │   │       ├── invitations/   # Invitation flow
│   │   │       ├── admin/         # Admin endpoints
│   │   │       ├── documents/     # Document upload & parsing
│   │   │       ├── github/        # GitHub repo connections
│   │   │       ├── agent_runs/    # AI agent execution
│   │   │       ├── crawls/        # DOM crawl sessions
│   │   │       └── events/        # SSE real-time events
│   │   ├── api/dependencies/      # FastAPI DI (project_access)
│   │   ├── middleware/             # rate_limit, rbac, tenant_context
│   │   ├── patterns/              # Reusable integration patterns
│   │   │   ├── llm_pattern.py     # LiteLLM wrapper (chat, streaming, token counting)
│   │   │   ├── pgvector_pattern.py # Vector embedding storage & similarity search
│   │   │   ├── sse_pattern.py     # Server-Sent Events streaming
│   │   │   └── playwright_pattern.py # Browser automation for DOM crawling
│   │   ├── services/              # Business logic
│   │   │   ├── agents/            # AI agent implementations
│   │   │   │   ├── orchestrator.py      # Pipeline orchestration
│   │   │   │   ├── ba_consultant.py     # Business Analyst agent
│   │   │   │   ├── qa_consultant.py     # QA Consultant agent
│   │   │   │   └── automation_consultant.py # Automation agent
│   │   │   ├── agent_run_service.py     # Agent execution lifecycle
│   │   │   ├── auth/auth_service.py     # Authentication (JWT, OAuth, Argon2id)
│   │   │   ├── document_service.py      # Document CRUD
│   │   │   ├── embedding_service.py     # Vector embedding generation
│   │   │   ├── github_connector_service.py # GitHub API integration
│   │   │   ├── source_code_analyzer_service.py # Code analysis
│   │   │   ├── dom_crawler_service.py   # Playwright DOM crawling
│   │   │   ├── sse_manager.py           # SSE connection management
│   │   │   ├── token_budget_service.py  # Token budget enforcement
│   │   │   └── ...                      # tenant, project, user, notification, etc.
│   │   ├── config.py              # App configuration (env-based)
│   │   ├── main.py                # FastAPI app entry point
│   │   ├── db.py                  # Database session management
│   │   ├── cache.py               # Redis cache layer
│   │   ├── health.py              # Health check endpoints
│   │   ├── metrics.py             # Prometheus metrics
│   │   └── logger.py              # Structured logging
│   ├── tests/
│   │   ├── unit/services/         # Service-level unit tests
│   │   ├── integration/           # API integration tests
│   │   ├── security/              # Security-focused tests
│   │   └── patterns/              # Pattern spike tests
│   └── requirements.txt           # Python dependencies
├── web/                            # React frontend (Vite + TS + Tailwind + shadcn/ui)
├── infrastructure/
│   ├── terraform/                 # Multi-cloud IaC (aws/ and azure/ roots)
│   └── kubernetes/                # K8s manifests (shared/, aws/, azure/)
├── e2e/                            # End-to-end test suites
├── .github/                        # GitHub Actions CI/CD workflows
├── compose.yml                     # Podman Compose local dev (5 services)
├── docs/                           # Project documentation
│   ├── planning/                  # PRD, product brief, UX design, agent specs
│   ├── architecture/              # System architecture (3,600+ lines)
│   ├── epics/                     # 8 epics with 132 stories
│   ├── tech-specs/                # Per-epic technical specifications
│   ├── stories/epic-{n}/          # Story files organised by epic
│   ├── evaluations/               # Agent Skills architecture evaluations
│   ├── reports/                   # Validation and readiness reports
│   └── research/                  # Market and competitive research
└── .bmad/                          # BMad Method v6 framework
```

## Established Patterns

### API Router Convention

Each domain lives in `backend/src/api/v1/{domain}/` with three files:
- `__init__.py` — empty
- `router.py` — FastAPI router with endpoints
- `schemas.py` — Pydantic request/response models

Routers use `APIRouter(prefix="/{domain}", tags=["{Domain}"])`.

### Service Layer Convention

- One class per service, instantiated as module-level singleton or via DI
- Async methods for all I/O operations
- Raise `HTTPException` for API-visible errors or custom domain exceptions
- Type hints on all parameters and return values

### Pattern Spikes (backend/src/patterns/)

Reusable abstractions proven during Epic 2 pattern spike phase:
- **llm_pattern.py** — `LLMPattern` wrapping `litellm` for chat completions, streaming, token counting
- **pgvector_pattern.py** — `PgVectorPattern` for embedding storage, similarity search, CRUD
- **sse_pattern.py** — `SSEPattern` for server-sent event streaming to frontend
- **playwright_pattern.py** — `PlaywrightPattern` for headless browser DOM crawling

### Test Convention

- **Unit tests:** `backend/tests/unit/services/test_{service_name}.py`
- **Integration tests:** `backend/tests/integration/test_{feature_name}.py`
- **Security tests:** `backend/tests/security/test_{feature}_security.py`
- **Pattern tests:** `backend/tests/patterns/test_{pattern}_pattern.py`
- Run with: `python -m pytest backend/tests/ -v`
- All tests must pass 100% before a story can move to review

### Multi-Tenancy

- Schema-per-tenant PostgreSQL with Row-Level Security
- Tenant isolation via `tenant_context` middleware (ContextVar-based)
- Organization-scoped data access at middleware + service layer
- Project access controlled via `project_access` dependency

### Local Development

- `podman-compose up -d` starts 5 services (PostgreSQL, Redis, MailCatcher, API, Web)
- Web: `http://localhost:3000`, API: `http://localhost:8000`, Mail: `http://localhost:1080`
- Docker Desktop is NOT approved — use Podman Desktop or `podman-compose` CLI

## Key Project Documents

| Document | Path |
|----------|------|
| BMM Config | `.bmad/bmm/config.yaml` |
| Workflow Status | `docs/bmm-workflow-status.yaml` |
| Sprint Status | `docs/sprint-status.yaml` |
| PRD (147 FRs) | `docs/planning/prd.md` |
| Architecture (3,600+ lines) | `docs/architecture/architecture.md` |
| UX Design | `docs/planning/ux-design-specification.md` |
| Agent Specifications | `docs/planning/agent-specifications.md` |
| Epics (8 epics, 132 stories) | `docs/epics/epics.md` |
| Epic tech specs | `docs/tech-specs/tech-spec-epic-{n}.md` |
| Stories | `docs/stories/{epic-id}/{story-id}.md` |
| Story context | `docs/stories/{epic-id}/{story-id}.context.xml` |
| Test Design System | `docs/planning/test-design-system.md` |
| Agent Skills Technical Review | `docs/evaluations/anthropic-agent-skills-technical-review.md` |
| Agent Skills Architecture Board | `docs/evaluations/anthropic-agent-skills-architecture-board.md` |

## Target Users (6 Personas)

| Persona | Primary Value |
|---------|-------------|
| Owner/Admin | Full platform control, billing, compliance, agent configuration |
| PM/CSM | Project oversight, SLA management, stakeholder reporting |
| QA-Manual | Guided manual test execution with evidence capture |
| QA-Automation | AI-powered test generation and self-healing management |
| Dev | Test results visibility integrated into development workflow |
| Viewer | Read-only access to quality metrics and reports |

## Current State (update as project progresses)

- **Track:** Enterprise BMad Method
- **Completed epics:** 0 (22 stories), 1 (13 stories)
- **Active epic:** 2 — AI Agent Platform & Executive Visibility
- **Total stories:** 132 (100 MVP + 32 Post-MVP)
- **Stories completed:** 35 of 132 (~26%)
- **Config user:** Azfar
- **Config language:** English
