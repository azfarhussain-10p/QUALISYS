<div align="center">

# Technical Specification — Epic 2: AI Agent Platform & Executive Visibility

**QUALISYS — AI System Quality Assurance Platform**

</div>

| Attribute | Detail |
|-----------|--------|
| **Epic** | 2 — AI Agent Platform & Executive Visibility |
| **Author** | Azfar |
| **Date** | 2026-02-26 |
| **Status** | Draft |
| **Duration** | 3–4 weeks |
| **Stories** | 18 stories (2-1 through 2-18) |
| **FRs Covered** | FR16–FR40, FR67–FR71, FR78–FR84 (40 FRs) |
| **Risk Level** | 🔴 Critical — LLM costs, latency, integration brittleness |
| **Dependencies** | Epic 1 (Foundation & Administration — completed) |
| **Previous Tech Spec** | `docs/tech-specs/tech-spec-epic-1.md` |

---

### Stakeholder Guide

| Stakeholder | Sections of Interest | Purpose |
|-------------|---------------------|---------|
| **QA-Automation / PM/CSM** | Sections 1–2, 8 | AI agent capabilities, JIRA sync, dashboard metrics |
| **Architect / Tech Lead** | Sections 3–5, 7 | AI stack, data models, API design, NFRs |
| **Engineering Team** | Sections 4–5, 8 | Services, APIs, sequencing, acceptance criteria |
| **QA Lead / TEA** | Sections 6, 8, 10 | NFRs, ACs, test strategy |
| **Owner / Admin** | Sections 1–2, 9 | Scope, risks, cost controls |

---

### Table of Contents

**Part I — Overview & Architecture**
- [1. Overview](#1-overview)
- [2. Objectives & Scope](#2-objectives--scope)
- [3. System Architecture Alignment](#3-system-architecture-alignment)

**Part II — Detailed Design**
- [4. Services, Data Models & APIs](#4-services-data-models--apis)
- [5. Workflows & Sequencing](#5-workflows--sequencing)

**Part III — Quality Attributes**
- [6. Non-Functional Requirements](#6-non-functional-requirements)
- [7. Dependencies & Integrations](#7-dependencies--integrations)

**Part IV — Validation & Governance**
- [8. Acceptance Criteria](#8-acceptance-criteria)
- [9. Traceability Mapping](#9-traceability-mapping)
- [10. Risks, Assumptions & Open Questions](#10-risks-assumptions--open-questions)
- [11. Test Strategy](#11-test-strategy)

---

# Part I — Overview & Architecture

---

## 1. Overview

Epic 2 delivers the **core value engine** of QUALISYS: AI-powered test generation from uploaded requirements documents, code repositories, and live application crawling. This epic transforms QUALISYS from a foundation platform into a demonstrable, AI-driven testing tool — the "magic moment" where platform value becomes tangible to every persona.

**Business Context:**
- **Core Value Unlock:** QA-Automation users upload a PRD, connect a GitHub repo, and receive 100+ generated test scenarios, manual checklists, and Playwright scripts within 10 minutes.
- **Executive Visibility:** PM/CSM dashboard surfaces real test coverage %, trend lines, and project health to leadership — the foundation for upsell and retention.
- **Integration-First Strategy:** Bi-directional JIRA sync proves the platform integrates into existing enterprise toolchains — the #1 purchase criterion for B2B SaaS.
- **Cost Control Architecture:** Token budget enforcement and Redis LLM caching are critical risk mitigations — cost spiral is the highest-risk failure mode for this epic.

**Key Deliverables:**
- Document ingestion pipeline (PDF, DOCX, Markdown → text → vector embeddings)
- GitHub repository connection + source code analysis (routes, endpoints, components)
- Playwright-based DOM crawling with authentication flow support
- 3-agent AI execution pipeline (BAConsultant → QAConsultant → AutomationConsultant) via LangChain
- Real-time agent progress via Server-Sent Events (SSE)
- Test artifact storage, viewer, and Monaco editor with version history
- PM/CSM project health dashboard with coverage metrics (Recharts + SSE refresh)
- JIRA integration: connect, import issues, bi-directional traceability
- Token budget monitoring dashboard for Admins

**Dependencies from Epic 1:**
- Auth system (JWT sessions, RBAC, `require_role()`, `require_project_role()`)
- Multi-tenant schema pattern (`tenant_{slug}`, `current_tenant_slug` ContextVar)
- Project model (`projects` table, `project_members` table)
- Audit logging service (`AuditService.log_action_async()`)
- Notification service (`NotificationService`)
- Background job runner (`arq`)

---

## 2. Objectives & Scope

### In Scope

**Document Ingestion & Analysis (FR16–FR25):**
- Upload PDF (max 25MB), DOCX, Markdown files per project
- Parse text: PyPDF2 (PDF), python-docx (DOCX), direct read (MD)
- Chunk into 1000-token segments with 200-token overlap
- Generate OpenAI `text-embedding-ada-002` embeddings (1536-dim)
- Store embeddings in pgvector extension (`document_embeddings` table)
- GitHub repository connection with personal access token (read-only)
- Repo clone to tenant-scoped temp directory (auto-cleanup after 7 days)
- Source code analysis: routes/endpoints (Express.js, FastAPI, Spring Boot), React components
- Application DOM crawling via Playwright headless (max 100 pages, 30-min timeout)
- Auth flow handling during crawl (login form fill, cookie capture)
- Ingestion summary view (documents, code files, pages crawled)

**AI Agent Orchestration (FR26–FR31):**
- Agent selection UI: 3 MVP agents (BAConsultant, QAConsultant, AutomationConsultant) with description cards
- Pipeline mode: Sequential (default) or Parallel
- Agent execution engine: LangChain chains with project context injection
- LLM token usage tracking per agent, per tenant
- Agent output (JSON) stored as artifacts in database
- Real-time progress via SSE (Queued → Running → Complete status cards)

**Test Artifact Generation (FR32–FR40):**
- BAConsultant: Requirements coverage matrix, gap/ambiguity detection, user story quality scoring
- QAConsultant: Manual checklists (Smoke, Sanity, Integration, Regression, Usability, UAT), exploratory prompts, BDD/Gherkin, negative/boundary cases, synthetic test data
- AutomationConsultant: Playwright scripts (TypeScript, POM/Data-Driven/Hybrid), smart locators
- Artifact viewer: tabs (Coverage Matrix, Manual Checklists, Playwright Scripts, BDD Scenarios) with syntax highlighting
- Monaco editor for in-line editing; new version on save; version history with diff view

**PM/CSM Dashboard (FR67–FR71):**
- Project health overview: health indicator (Green/Yellow/Red), coverage %, recent activity
- Coverage widget: requirements covered vs total, trend line chart (Recharts), configurable target, drill-down to coverage matrix
- Placeholder widgets for Epic 3–4 metrics (execution velocity, defect leakage) — "Coming Soon"
- Auto-refresh via SSE (30-second interval)

**JIRA Integration (FR78–FR84):**
- Admin connects JIRA via API key/username (Atlassian API, not OAuth for MVP)
- Encrypted credential storage (`credentials_encrypted` column)
- Test connection validation (`/rest/api/2/myself`)
- Import JIRA issues by project + issue types (background job)
- Bi-directional link: test case ↔ JIRA issue (stored in `jira_traceability` table)
- FR82–FR84 (auto create/update JIRA issues on test failure/pass): **deferred to Epic 3–4** via placeholder

**Token Budget Monitoring (Admin, Story 2-18):**
- Admin dashboard page: monthly token usage breakdown by agent, cost estimation, alert at 80%, hard limit enforcement at 100%

### Out of Scope (Epic 2)

- GitHub webhook integration (Epic 3)
- Manual test execution interface (Epic 3)
- JIRA auto-defect creation on test failure (Epic 3–4)
- JIRA issue status update on test pass (Epic 4)
- SAML 2.0 for JIRA OAuth (MVP uses API key auth)
- Drag-and-drop pipeline builder (Epic 6+)
- Post-MVP agents: AI Log Reader, Security Scanner, Performance Agent, DatabaseConsultant (Epic 6+)
- Self-hosted LLM (Ollama / vLLM) (Epic 6+)
- Agent extensibility / custom agents (Epic 6+)
- TestRail integration (Epic 5+)

---

## 3. System Architecture Alignment

Epic 2 activates the **AI/LLM Layer** and **Integration Gateway** components defined in the architecture, while extending the **Core Services** layer established in Epic 1.

### Architecture Components Activated

| Component | Architecture Reference | Epic 2 Role |
|-----------|----------------------|-------------|
| `AI Agent Orchestrator` | `services/agents/orchestrator.py` | LangChain pipeline: BAConsultant → QAConsultant → AutomationConsultant |
| `pgvector` | PostgreSQL extension | Document embedding storage and similarity search |
| `BullMQ` (replaced by `arq` in current stack) | Background job runner | Document parsing, embedding generation, JIRA import, DOM crawl |
| `Integration Gateway` | `services/integrations/` | JIRA client with DLQ + retry pattern |
| `SSE Client` | `/api/v1/events/agent-runs/{run_id}` | Real-time agent execution progress |
| `Token Budget Control` | `core/llm_provider.py`, Redis | Per-tenant atomic token counters, 80% alert, 100% hard limit |
| `Object Storage (S3)` | `boto3` | Uploaded document storage, clone directories (deferred to Epic 3 for screenshots) |

### Multi-Tenancy Constraints

All Epic 2 data follows the **schema-per-tenant** pattern established in Epic 1:

- Tenant context: `current_tenant_slug` ContextVar set by `TenantContextMiddleware`
- Schema: `slug_to_schema_name(current_tenant_slug.get())` → `tenant_{slug}`
- All queries: `text(f'SELECT ... FROM "{schema_name}".table WHERE ...')`
- GitHub clone directories: `tmp/tenants/{tenant_id}/repos/{repo_slug}/` (filesystem isolation)
- Token budgets: Redis key `budget:{tenant_id}:monthly` (atomic counter)

### LLM Strategy (MVP)

| LLM | Role | Constraint |
|-----|------|-----------|
| OpenAI `gpt-4-turbo` | Primary agent reasoning | Hard token budget per tenant |
| OpenAI `text-embedding-ada-002` | Document embeddings | Counted toward token budget |
| Anthropic Claude (fallback) | Long-context tasks if GPT-4 fails | Circuit breaker trigger |
| vLLM (self-hosted) | Planned Epic 6+ | Not in MVP |

**Token Budget Tiers (from Architecture):**
- Free: 1,000 tokens/day
- Pro: 10,000 tokens/day
- Enterprise: 100,000 tokens/day

**Redis Caching Strategy:**
- Cache key: `llm:cache:{sha256(prompt)}` → TTL 24h
- Hit avoids LLM call entirely; critical for identical re-runs

---

# Part II — Detailed Design

---

## 4. Services, Data Models & APIs

### 4.1 Services & Modules

| Service | File Path | Responsibility |
|---------|-----------|---------------|
| `DocumentService` | `backend/src/services/document_service.py` | Upload, parse (PDF/DOCX/MD), preview, list per project |
| `EmbeddingService` | `backend/src/services/embedding_service.py` | Chunk text, call OpenAI embeddings API, store in pgvector |
| `GitHubConnectorService` | `backend/src/services/github_connector_service.py` | Token validation, repo clone, cleanup scheduler |
| `SourceCodeAnalyzerService` | `backend/src/services/source_code_analyzer_service.py` | Route/endpoint/component extraction, analysis summary |
| `DOMCrawlerService` | `backend/src/services/dom_crawler_service.py` | Playwright headless crawl, auth flow, page structure capture |
| `AgentOrchestrator` | `backend/src/services/agents/orchestrator.py` | LangChain chain assembly, context injection, token tracking |
| `BAConsultantAgent` | `backend/src/services/agents/ba_consultant.py` | Coverage matrix + gap analysis via LLM |
| `QAConsultantAgent` | `backend/src/services/agents/qa_consultant.py` | Manual checklists, BDD, exploratory prompts via LLM |
| `AutomationConsultantAgent` | `backend/src/services/agents/automation_consultant.py` | Playwright script generation via LLM |
| `AgentRunService` | `backend/src/services/agent_run_service.py` | Pipeline creation, SSE event emission, run status tracking |
| `ArtifactService` | `backend/src/services/artifact_service.py` | CRUD artifacts, versioning, diff computation |
| `PMDashboardService` | `backend/src/services/pm_dashboard_service.py` | Coverage % calculation, trend aggregation, SSE refresh |
| `JIRAIntegrationService` | `backend/src/services/jira_integration_service.py` | Connect, test-connection, import issues, DLQ retry, traceability |
| `TokenBudgetService` | `backend/src/services/token_budget_service.py` | Redis atomic counters, budget check, 80% alert, hard limit |
| `LLMProviderService` | `backend/src/services/llm_provider_service.py` | Multi-provider abstraction (OpenAI primary, Anthropic fallback), cache wrapper |

### 4.2 New Database Migrations (starting at 013)

**Migration 013 — Enable pgvector + Document Tables**

```sql
-- Per-tenant schema (iterate all tenant_% schemas)
CREATE EXTENSION IF NOT EXISTS vector SCHEMA public;  -- once globally

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename        VARCHAR(255) NOT NULL,
    file_type       VARCHAR(20) NOT NULL,  -- pdf, docx, md
    file_size_bytes INTEGER NOT NULL,
    s3_key          TEXT NOT NULL,         -- S3 object key
    parse_status    VARCHAR(50) NOT NULL DEFAULT 'pending',
                                           -- pending, processing, completed, failed
    parsed_text     TEXT,                  -- full extracted text
    preview_text    TEXT,                  -- first 500 chars
    page_count      INTEGER,
    chunk_count     INTEGER DEFAULT 0,
    error_message   TEXT,
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE document_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content     TEXT NOT NULL,             -- 1000-token chunk content
    token_count INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE document_embeddings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id    UUID NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    embedding   vector(1536),              -- OpenAI text-embedding-ada-002
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_documents_project_id ON documents(project_id);
CREATE INDEX idx_documents_parse_status ON documents(parse_status);
CREATE INDEX idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_document_embeddings_vector
    ON document_embeddings USING ivfflat (embedding vector_cosine_ops);
```

**Migration 014 — GitHub Connections + DOM Crawl Sessions**

```sql
CREATE TABLE github_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    repo_url        VARCHAR(500) NOT NULL,
    encrypted_token TEXT NOT NULL,         -- AES-encrypted PAT
    clone_path      TEXT,                  -- Filesystem path (temp)
    status          VARCHAR(50) NOT NULL DEFAULT 'connected',
                                           -- connected, cloning, analyzed, failed, expired
    routes_count    INTEGER DEFAULT 0,
    components_count INTEGER DEFAULT 0,
    endpoints_count INTEGER DEFAULT 0,
    analysis_summary JSONB,                -- {routes: [...], components: [...], endpoints: [...]}
    expires_at      TIMESTAMPTZ,           -- 7-day auto-cleanup
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE crawl_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    target_url      VARCHAR(2000) NOT NULL,
    auth_config     JSONB,                 -- {login_url, username_selector, password_selector, credentials_encrypted}
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
                                           -- pending, running, completed, failed, timeout
    pages_crawled   INTEGER DEFAULT 0,
    forms_found     INTEGER DEFAULT 0,
    links_found     INTEGER DEFAULT 0,
    crawl_data      JSONB,                 -- full captured DOM structure
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_github_connections_project_id ON github_connections(project_id);
CREATE INDEX idx_crawl_sessions_project_id ON crawl_sessions(project_id);
```

**Migration 015 — Agent Runs + Artifacts**

```sql
CREATE TABLE agent_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pipeline_mode   VARCHAR(20) NOT NULL DEFAULT 'sequential',  -- sequential, parallel
    agents_selected JSONB NOT NULL,        -- ["ba_consultant", "qa_consultant", "automation_consultant"]
    status          VARCHAR(50) NOT NULL DEFAULT 'queued',
                                           -- queued, running, completed, failed, cancelled
    total_tokens    INTEGER DEFAULT 0,
    total_cost_usd  NUMERIC(10, 4) DEFAULT 0,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE agent_run_steps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    agent_type      VARCHAR(50) NOT NULL,  -- ba_consultant, qa_consultant, automation_consultant
    status          VARCHAR(50) NOT NULL DEFAULT 'queued',
    progress_pct    INTEGER DEFAULT 0,
    progress_label  TEXT,                  -- "Analyzing page 23 of 47..."
    tokens_used     INTEGER DEFAULT 0,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT
);

CREATE TABLE artifacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    run_id          UUID REFERENCES agent_runs(id),
    agent_type      VARCHAR(50) NOT NULL,
    artifact_type   VARCHAR(100) NOT NULL, -- coverage_matrix, manual_checklist, playwright_script, bdd_scenario
    title           VARCHAR(255) NOT NULL,
    current_version INTEGER NOT NULL DEFAULT 1,
    metadata        JSONB,                 -- {tokens_used, requirements_covered, ...}
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE artifact_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    version     INTEGER NOT NULL,
    content     TEXT NOT NULL,             -- raw content (JSON, Gherkin, TypeScript, etc.)
    content_type VARCHAR(50) NOT NULL,     -- application/json, text/plain, text/typescript
    diff_from_prev TEXT,                   -- unified diff string vs previous version
    edited_by   UUID REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (artifact_id, version)
);

CREATE INDEX idx_agent_runs_project_id ON agent_runs(project_id);
CREATE INDEX idx_agent_runs_status ON agent_runs(status);
CREATE INDEX idx_agent_run_steps_run_id ON agent_run_steps(run_id);
CREATE INDEX idx_artifacts_project_id ON artifacts(project_id);
CREATE INDEX idx_artifacts_artifact_type ON artifacts(artifact_type);
CREATE INDEX idx_artifact_versions_artifact_id ON artifact_versions(artifact_id);
```

**Migration 016 — JIRA Integration**

```sql
CREATE TABLE jira_connections (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    jira_base_url       VARCHAR(500) NOT NULL,   -- https://myteam.atlassian.com
    api_username        VARCHAR(255) NOT NULL,    -- email
    credentials_encrypted TEXT NOT NULL,         -- AES-encrypted API key
    status              VARCHAR(50) NOT NULL DEFAULT 'connected',
                                                 -- connected, failed, disconnected
    last_test_at        TIMESTAMPTZ,
    last_sync_at        TIMESTAMPTZ,
    sync_error_count    INTEGER DEFAULT 0,
    created_by          UUID NOT NULL REFERENCES users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE jira_issues (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    jira_connection_id UUID NOT NULL REFERENCES jira_connections(id),
    jira_id         VARCHAR(50) NOT NULL,        -- e.g. PROJ-123
    jira_key        VARCHAR(50) NOT NULL,
    issue_type      VARCHAR(50) NOT NULL,        -- Story, Bug, Task
    summary         TEXT NOT NULL,
    description     TEXT,
    status          VARCHAR(100),
    assignee        VARCHAR(255),
    jira_url        TEXT,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, jira_id)
);

CREATE TABLE jira_traceability (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id     UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    jira_issue_id   UUID NOT NULL REFERENCES jira_issues(id) ON DELETE CASCADE,
    linked_by       UUID NOT NULL REFERENCES users(id),
    linked_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (artifact_id, jira_issue_id)
);

CREATE TABLE jira_sync_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID NOT NULL REFERENCES jira_connections(id),
    operation   VARCHAR(50) NOT NULL,  -- import, webhook, retry
    status      VARCHAR(50) NOT NULL,  -- success, failed, retrying
    details     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_jira_connections_project_id ON jira_connections(project_id);
CREATE INDEX idx_jira_issues_project_id ON jira_issues(project_id);
CREATE INDEX idx_jira_issues_jira_id ON jira_issues(jira_id);
CREATE INDEX idx_jira_traceability_artifact_id ON jira_traceability(artifact_id);
```

### 4.3 API Endpoints

**Document Ingestion — `POST /api/v1/projects/{project_id}/documents`**

```
POST   /api/v1/projects/{project_id}/documents         # Upload document (multipart/form-data)
GET    /api/v1/projects/{project_id}/documents         # List documents
GET    /api/v1/projects/{project_id}/documents/{id}    # Document detail + parse status
DELETE /api/v1/projects/{project_id}/documents/{id}    # Delete document

POST   /api/v1/projects/{project_id}/github            # Connect GitHub repo
GET    /api/v1/projects/{project_id}/github            # GitHub connection status + analysis summary
DELETE /api/v1/projects/{project_id}/github            # Disconnect GitHub

POST   /api/v1/projects/{project_id}/crawls            # Start DOM crawl
GET    /api/v1/projects/{project_id}/crawls            # List crawl sessions
GET    /api/v1/projects/{project_id}/crawls/{id}       # Crawl session detail
```

**Agent Execution — `/api/v1/projects/{project_id}/agent-runs`**

```
GET    /api/v1/agents                                         # List available agents (definitions)
POST   /api/v1/projects/{project_id}/agent-runs               # Create + start pipeline run
GET    /api/v1/projects/{project_id}/agent-runs               # List runs for project
GET    /api/v1/projects/{project_id}/agent-runs/{run_id}      # Run status + steps
DELETE /api/v1/projects/{project_id}/agent-runs/{run_id}      # Cancel run

# SSE — real-time progress
GET    /api/v1/events/agent-runs/{run_id}                     # SSE stream (Content-Type: text/event-stream)
```

**SSE event format:**
```json
{
  "event": "agent_step_update",
  "data": {
    "run_id": "uuid",
    "agent_type": "ba_consultant",
    "status": "running",
    "progress_pct": 47,
    "progress_label": "Analyzing requirement 23 of 47...",
    "tokens_used": 4231
  }
}
```

**Artifacts — `/api/v1/projects/{project_id}/artifacts`**

```
GET    /api/v1/projects/{project_id}/artifacts                # List all artifacts (filter by type)
GET    /api/v1/projects/{project_id}/artifacts/{id}           # Artifact detail + current version content
GET    /api/v1/projects/{project_id}/artifacts/{id}/versions  # Version history
GET    /api/v1/projects/{project_id}/artifacts/{id}/versions/{v} # Specific version content
PUT    /api/v1/projects/{project_id}/artifacts/{id}           # Save edit (creates new version)
```

**PM Dashboard — `/api/v1/projects/{project_id}/dashboard`**

```
GET    /api/v1/projects/{project_id}/dashboard/overview       # Health indicator, coverage %, activity
GET    /api/v1/projects/{project_id}/dashboard/coverage       # Coverage % detail + trend time series
GET    /api/v1/dashboard/projects                             # Multi-project health grid (PM/CSM)

# SSE — auto-refresh
GET    /api/v1/events/dashboard/{project_id}                  # SSE stream (30s heartbeat)
```

**JIRA Integration — `/api/v1/projects/{project_id}/integrations/jira`**

```
POST   /api/v1/projects/{project_id}/integrations/jira        # Connect JIRA
GET    /api/v1/projects/{project_id}/integrations/jira        # Connection status
POST   /api/v1/projects/{project_id}/integrations/jira/test   # Test connection (GET /myself)
DELETE /api/v1/projects/{project_id}/integrations/jira        # Disconnect

POST   /api/v1/projects/{project_id}/integrations/jira/import # Start JIRA issue import (background job)
GET    /api/v1/projects/{project_id}/jira-issues              # List imported issues
GET    /api/v1/projects/{project_id}/jira-issues/{issue_id}   # Issue detail

POST   /api/v1/projects/{project_id}/artifacts/{id}/jira-link # Link artifact ↔ JIRA issue
DELETE /api/v1/projects/{project_id}/artifacts/{id}/jira-link/{jira_issue_id} # Unlink
GET    /api/v1/projects/{project_id}/artifacts/{id}/jira-links # List all links for artifact
```

**Token Budget — `/api/v1/admin/token-usage`**

```
GET    /api/v1/admin/token-usage              # Monthly usage totals, breakdown by agent, cost estimate
GET    /api/v1/admin/token-usage/history      # Daily usage time series (last 30 days)
```

### 4.4 Request / Response Models (key schemas)

**DocumentUploadResponse:**
```json
{
  "id": "uuid",
  "filename": "requirements.pdf",
  "file_type": "pdf",
  "file_size_bytes": 1234567,
  "parse_status": "pending",
  "preview_text": null,
  "chunk_count": 0,
  "created_at": "2026-02-26T10:00:00Z"
}
```

**AgentRunCreateRequest:**
```json
{
  "pipeline_mode": "sequential",
  "agents": ["ba_consultant", "qa_consultant", "automation_consultant"]
}
```

**AgentRunResponse:**
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "pipeline_mode": "sequential",
  "status": "running",
  "steps": [
    { "agent_type": "ba_consultant", "status": "completed", "progress_pct": 100, "tokens_used": 12450 },
    { "agent_type": "qa_consultant", "status": "running",   "progress_pct": 47,  "tokens_used": 6231 },
    { "agent_type": "automation_consultant", "status": "queued", "progress_pct": 0, "tokens_used": 0 }
  ],
  "total_tokens": 18681,
  "total_cost_usd": "0.3736"
}
```

**ArtifactSaveRequest (editor):**
```json
{
  "content": "...edited TypeScript content...",
  "edit_note": "Fixed selector for login button"
}
```

---

## 5. Workflows & Sequencing

### 5.1 Document Ingestion Flow (Stories 2-1, 2-2)

```
User uploads file (POST /documents)
  │
  ├─ Backend validates: extension, size ≤ 25MB, MIME type
  ├─ S3 upload (boto3): documents/{tenant_id}/{project_id}/{uuid}/{filename}
  ├─ DB insert: documents (parse_status = 'pending')
  ├─ arq background job queued: parse_document(document_id)
  │
  └─ Background Job:
       ├─ Download from S3
       ├─ Parse:  PDF → PyPDF2 | DOCX → python-docx | MD → direct read
       ├─ Update: documents.parsed_text, preview_text, page_count, parse_status='processing'
       ├─ Chunk text: 1000-token windows, 200-token overlap
       ├─ Insert: document_chunks rows
       ├─ For each chunk:
       │    ├─ Check token budget (TokenBudgetService.check_and_reserve)
       │    ├─ Call OpenAI text-embedding-ada-002
       │    ├─ Track tokens used (TokenBudgetService.consume)
       │    └─ Insert: document_embeddings (vector 1536-dim)
       ├─ Update: documents.chunk_count, parse_status='completed'
       └─ On failure: documents.parse_status='failed', error_message set
```

### 5.2 GitHub Connection + Analysis Flow (Stories 2-3, 2-4)

```
User connects repo (POST /github)
  │
  ├─ Validate PAT: GET https://api.github.com/repos/{owner}/{repo} (httpx)
  ├─ DB insert: github_connections (status='cloning')
  ├─ arq job queued: clone_and_analyze_repo(connection_id)
  │
  └─ Background Job:
       ├─ git clone --depth=1 {repo_url} into tmp/tenants/{tenant_id}/repos/{uuid}/
       ├─ Schedule cleanup: expires_at = NOW() + 7 days
       ├─ Analyze codebase:
       │    ├─ Detect framework: FastAPI (main.py patterns), Express.js (router patterns), Spring Boot (annotations)
       │    ├─ Extract routes: regex/AST parsing per framework
       │    ├─ Extract React components: *.tsx/*.jsx file scan
       │    └─ Build analysis_summary JSON
       ├─ Update: github_connections.status='analyzed', routes_count, components_count, endpoints_count, analysis_summary
       └─ On failure: status='failed', error_message set
```

### 5.3 Agent Pipeline Execution Flow (Stories 2-6 through 2-10)

```
User starts pipeline (POST /agent-runs)
  │
  ├─ Validate: project has at least 1 document or github connection or crawl session
  ├─ Check global token budget: TokenBudgetService.check_budget(tenant_id)
  ├─ DB insert: agent_runs (status='queued'), agent_run_steps for each selected agent
  ├─ arq job queued: execute_agent_pipeline(run_id)
  │
  └─ Background Job (sequential mode):
       │
       ├─ Assemble context:
       │    ├─ Load document chunks (text, not vectors — vectors for similarity search only)
       │    ├─ Load github_connections.analysis_summary
       │    └─ Load crawl_sessions.crawl_data
       │
       ├─ For each agent in order:
       │    ├─ Update step status='running', emit SSE event
       │    ├─ Check Redis LLM cache: key = sha256(agent_type + context_hash)
       │    │    └─ Cache hit → return cached output, skip LLM call
       │    ├─ Build LangChain chain (system prompt + context injection)
       │    ├─ Stream LLM response with progress callbacks
       │    ├─ Emit SSE progress events (progress_pct, progress_label)
       │    ├─ TokenBudgetService.consume(tokens_used)
       │    │    └─ At 80%: send email alert (NotificationService)
       │    │    └─ At 100%: raise BudgetExceededError → cancel remaining agents
       │    ├─ Parse LLM JSON output → validate structure
       │    ├─ Insert artifact + artifact_version (version=1)
       │    ├─ Cache LLM response in Redis (TTL 24h)
       │    └─ Update step status='completed', emit SSE event
       │
       ├─ Update agent_runs.status='completed'
       └─ Emit SSE final event: { event: "run_complete", confetti: true }
```

### 5.4 JIRA Import Flow (Stories 2-15, 2-16)

```
Admin connects JIRA (POST /integrations/jira)
  │
  ├─ Validate form: JIRA URL, email, API key
  ├─ Encrypt API key: AES-256-GCM via cryptography library
  ├─ Test connection: httpx GET {jira_url}/rest/api/2/myself (Basic Auth: email:api_key)
  ├─ DB insert: jira_connections (status='connected')
  │
User imports issues (POST /integrations/jira/import)
  │
  ├─ arq job: import_jira_issues(connection_id, jira_project_key, issue_types)
  │
  └─ Background Job:
       ├─ httpx GET /rest/api/2/search?jql=project={key}+AND+issuetype+in+({types})
       ├─ Paginate (maxResults=100, startAt increments)
       ├─ Upsert: jira_issues (ON CONFLICT jira_id DO UPDATE)
       ├─ Log: jira_sync_logs (operation='import', status='success')
       └─ On failure: DLQ retry with exponential backoff
            Schedule: 1min → 5min → 30min → 2h → 12h (5 attempts, 7-day retention)
```

---

# Part III — Quality Attributes

---

## 6. Non-Functional Requirements

### 6.1 Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Document parse (1MB PDF) | < 10 seconds | Background job duration |
| Embedding generation (50-page PDF, ~150 chunks) | < 30 seconds | End-to-end background job |
| Agent pipeline P95 latency (40–50 requirements) | < 10 minutes | Run duration percentile |
| SSE event lag (server emit → client receive) | < 500ms | APM tracing |
| JIRA import (100 issues) | < 60 seconds | Background job duration |
| PM Dashboard API response | < 500ms | API p95 (Redis-cached) |
| Artifact list API response | < 300ms | API p95 |
| DOM crawl (50 pages) | < 15 minutes | Crawl session duration |

**Caching strategy:**
- LLM responses: Redis, key = `llm:cache:{sha256(agent_type + context_hash)}`, TTL 24h
- PM Dashboard metrics: Redis, key = `dashboard:{project_id}`, TTL 60s
- Agent definitions list: Redis, key = `agents:definitions`, TTL 1h (static config)

### 6.2 Security

| Control | Implementation |
|---------|---------------|
| Document IP protection | Documents stored in private S3 bucket with tenant-scoped paths; never sent to LLM without explicit consent prompt |
| JIRA API key encryption | AES-256-GCM via `cryptography` library; key stored in AWS Secrets Manager |
| GitHub PAT encryption | Same AES-256-GCM pattern; clone directories chmod 700, tenant-scoped |
| LLM prompt injection | Input sanitization on document content before prompt injection; max document size limit enforced pre-LLM |
| RBAC enforcement | `require_project_role("owner", "admin", "qa-automation")` on agent run and document endpoints; `require_role("owner", "admin")` on JIRA connect/token budget |
| Token budget hard limit | `TokenBudgetService.check_budget()` called before every LLM invocation; `BudgetExceededError` → HTTP 429 with `BUDGET_EXCEEDED` error code |
| GitHub repo clone isolation | Each tenant's repos under `tmp/tenants/{tenant_id}/` — no symlink traversal; 7-day auto-cleanup via arq scheduled job |
| Playwright crawl isolation | Playwright launched in subprocess per crawl session; timeout = 30 min; max 100 pages hard limit |
| CORS | No new CORS exceptions required; all API under `/api/v1/` |

### 6.3 Reliability / Availability

| Concern | Mitigation |
|---------|-----------|
| LLM API unavailability | Circuit breaker: 3 failures → switch to Anthropic Claude fallback (LLMProviderService) |
| LLM timeout | Retry 3x with 5s exponential backoff; after 3rd failure → `AgentStepError`, mark step `failed` |
| JIRA API down | Dead letter queue (Redis LIST); 5 retries over 24h; graceful degradation — show cached JIRA data |
| S3 upload failure | arq retry (3x); user sees `parse_status: 'failed'` with actionable error |
| DOM crawl timeout | Hard 30-minute timeout enforced in Playwright; partial results stored |
| Long agent runs | arq job TTL = 20 minutes; orphaned runs detected by heartbeat check and marked `failed` |
| Background job idempotency | All arq jobs check current DB state before proceeding (e.g., `if document.parse_status == 'completed': return`) |

### 6.4 Observability

| Signal | Implementation |
|--------|---------------|
| Structured logs | `python-json-logger`; all services log `tenant_id`, `project_id`, `run_id`, `agent_type` |
| Metrics (Prometheus) | `prometheus-fastapi-instrumentator`; custom counters: `llm_tokens_consumed_total{tenant,agent}`, `agent_run_duration_seconds`, `document_parse_duration_seconds`, `jira_import_issues_total` |
| Distributed tracing | OpenTelemetry spans: `document.parse`, `embedding.generate`, `agent.execute`, `jira.import` |
| LLM cost dashboard | Admin token-usage API surfaces `total_cost_usd` computed from token counts × OpenAI pricing |
| Loki logs | All arq background jobs log to structured stdout, captured by Loki |
| Alert thresholds | Prometheus alert: `llm_tokens_consumed_total > 0.8 * budget_limit` (80% alert, fires NotificationService) |

---

## 7. Dependencies & Integrations

### 7.1 New Backend Dependencies (add to `requirements.txt`)

```txt
# ---------------------------------------------------------------------------
# AI / LLM (Epic 2)
# ---------------------------------------------------------------------------
langchain==0.2.16
langchain-openai==0.1.25
openai==1.54.0
anthropic==0.34.2
sentence-transformers==3.1.1
pgvector==0.3.3                   # Python pgvector client for SQLAlchemy

# ---------------------------------------------------------------------------
# Document Parsing (Epic 2)
# ---------------------------------------------------------------------------
pypdf==4.3.1                      # PDF text extraction (replaces deprecated PyPDF2)
python-docx==1.1.2                # DOCX parsing
tiktoken==0.7.0                   # Token counting (OpenAI tokenizer)

# ---------------------------------------------------------------------------
# GitHub / DOM Crawling (Epic 2)
# ---------------------------------------------------------------------------
gitpython==3.1.43                 # Repo cloning
playwright==1.46.0                # DOM crawling (headless browser)
# Note: playwright install chromium required in container image (Epic 0 Dockerfile)

# ---------------------------------------------------------------------------
# JIRA Integration (Epic 2)
# ---------------------------------------------------------------------------
jira==3.8.0                       # Atlassian JIRA Python client
```

### 7.2 New Frontend Dependencies (add to `package.json`)

```json
"recharts": "^2.12.7",
"@monaco-editor/react": "^4.6.0",
"@radix-ui/react-tabs": "^1.1.0",
"@radix-ui/react-progress": "^1.1.0",
"@radix-ui/react-dialog": "^1.1.1",
"@radix-ui/react-select": "^2.1.1",
"react-diff-viewer-continued": "^3.4.0"
```

### 7.3 External Service Dependencies

| Service | Auth Method | Rate Limit | Failure Handling |
|---------|------------|------------|-----------------|
| OpenAI API (GPT-4, embeddings) | API Key (Secrets Manager) | Tier-dependent; retry on 429 | Exponential backoff; fallback to Anthropic |
| Anthropic API (Claude) | API Key (Secrets Manager) | Rate-limited per key | Fallback only; circuit breaker |
| AWS S3 | IAM Role (pod identity) | None | Retry (boto3 built-in) |
| GitHub REST API v3 | PAT (user-provided) | 5000 req/hr per token | Validate on connect; quota check before clone |
| JIRA REST API v2/v3 | Basic Auth (email + API key) | Atlassian Cloud rate limits | DLQ with exponential backoff (5 retries, 24h window) |

### 7.4 Internal Service Dependencies

| Service | Direction | Usage |
|---------|-----------|-------|
| `AuthService` (Epic 1) | Epic 2 consumes | JWT validation, tenant context |
| `ProjectService` (Epic 1) | Epic 2 consumes | `project_id` validation, RBAC check |
| `AuditService` (Epic 1) | Epic 2 consumes | Audit logging for agent runs, JIRA connect, document delete |
| `NotificationService` (Epic 1) | Epic 2 consumes | 80% token budget alert emails |
| `arq` job runner (Epic 1) | Epic 2 extends | New job functions for Epic 2 background tasks |

---

# Part IV — Validation & Governance

---

## 8. Acceptance Criteria

> Authoritative testable acceptance criteria, normalized from epics.md story ACs and PRD FRs.

**AC-01:** Upload endpoint accepts PDF, DOCX, MD files ≤ 25MB. Files > 25MB return `HTTP 400 FILE_TOO_LARGE`.

**AC-02:** PDF files parsed via PyPDF2/pypdf; DOCX via python-docx; Markdown as plain text. Extracted text stored in `documents.parsed_text`.

**AC-03:** Parsed document preview (first 500 characters) returned in GET /documents/{id} as `preview_text`.

**AC-04:** PDF parse errors (e.g. scanned/image-only PDF) set `parse_status = 'failed'` with `error_message = "Could not extract text. Upload Markdown for better results."`.

**AC-05:** Document text chunked into 1000-token segments with 200-token overlap. Chunks stored in `document_chunks`.

**AC-06:** OpenAI `text-embedding-ada-002` embeddings (1536-dim) generated for all chunks and stored in `document_embeddings` via pgvector.

**AC-07:** Embedding generation progress emitted as background job log: `"Processing chunk {n} of {total}"`.

**AC-08:** Token usage from embedding generation counted against tenant's monthly budget.

**AC-09:** GitHub connection form validates PAT via GitHub API (`/repos/{owner}/{repo}` → 200 OK). Invalid tokens return `HTTP 400 INVALID_TOKEN`.

**AC-10:** Connected repo cloned to tenant-scoped temp directory with 7-day expiry. Directory cleaned up by scheduled arq job.

**AC-11:** Source code analysis extracts routes/endpoints and component structure. Summary shown: `"47 routes, 23 components, 12 API endpoints"`.

**AC-12:** DOM crawl accepts target URL and optional login credentials. Playwright crawls max 100 pages (breadth-first), timeout 30 minutes.

**AC-13:** Crawl auth flow fills login form selectors provided by user; captures cookies for authenticated pages.

**AC-14:** Crawl summary displays: `"Crawled {n} pages, {f} forms, {l} links"`.

**AC-15:** Agent selection page shows 3 MVP agents (BAConsultant, QAConsultant, AutomationConsultant) with icon, name, description, required inputs, expected outputs.

**AC-16:** Agent pipeline started with one click ("Run Selected Agents"). Default mode = sequential.

**AC-17:** Agent execution checks token budget before starting. If budget exceeded, returns `HTTP 429 BUDGET_EXCEEDED` with message: `"Monthly token budget exceeded. Contact your admin."`.

**AC-18:** LLM responses cached in Redis (TTL 24h, key = sha256(agent_type + context_hash)). Cache hit skips LLM API call.

**AC-19:** SSE stream `/api/v1/events/agent-runs/{run_id}` emits `agent_step_update` events with `status`, `progress_pct`, `progress_label`, `tokens_used` per agent step.

**AC-20:** Agent progress UI shows status cards: Queued (gray) → Running (blue, animated) → Complete (green). Progress bar per agent.

**AC-21:** On run completion: success animation displayed. Artifacts page loads automatically.

**AC-22:** BAConsultant generates requirements coverage matrix (requirements × test scenarios) stored as `artifact_type = 'coverage_matrix'`.

**AC-23:** QAConsultant generates manual test checklists (min 1 per requirement) stored as `artifact_type = 'manual_checklist'`.

**AC-24:** AutomationConsultant generates Playwright TypeScript scripts stored as `artifact_type = 'playwright_script'`. Scripts are syntactically valid TypeScript.

**AC-25:** QAConsultant generates BDD/Gherkin scenarios (Given/When/Then) stored as `artifact_type = 'bdd_scenario'`.

**AC-26:** Artifact viewer shows tabs: Coverage Matrix, Manual Checklists, Playwright Scripts, BDD Scenarios. Each artifact shows: created by (agent name), created at, tokens used, version.

**AC-27:** Monaco editor opens on "Edit" button. Supports syntax highlighting for TypeScript (Playwright), Gherkin (BDD), Markdown (checklists).

**AC-28:** Saving edits in Monaco creates a new artifact version (`version` incremented). Previous versions accessible via version history dropdown.

**AC-29:** Diff view shows unified diff between any two artifact versions.

**AC-30:** PM Dashboard displays project health: coverage % indicator (Green ≥ 80%, Yellow 50–79%, Red < 50%) and recent activity.

**AC-31:** Coverage widget shows `"N of M requirements covered (X%)"` with trend line chart (Recharts, last 30 days), configurable target line.

**AC-32:** Dashboard auto-refreshes coverage % via SSE (30-second heartbeat).

**AC-33:** Execution velocity and defect leakage widgets show "Coming Soon" placeholder text (grayed out).

**AC-34:** JIRA connection form accepts JIRA URL, API username (email), API key. "Test Connection" calls Atlassian `/myself` endpoint. Success = green "Connected" status, failure = error message.

**AC-35:** JIRA API key stored encrypted at rest (AES-256-GCM). Key never returned in API responses.

**AC-36:** JIRA issue import runs as background job. Progress notification shown. On completion: `"✅ Successfully imported {n} issues"`.

**AC-37:** Imported JIRA issues displayed in Requirements tab with JIRA ID, title, description, issue type.

**AC-38:** "Link to JIRA" button on artifact opens search dialog. Type JIRA ID or search by title. Creates `jira_traceability` record.

**AC-39:** Linked JIRA issues shown as badges on artifact cards.

**AC-40:** Admin token usage dashboard shows: monthly total tokens, breakdown by agent, cost estimate (tokens × OpenAI pricing), alert at 80%, hard limit at 100%.

---

## 9. Traceability Mapping

| AC | PRD FR | Architecture Section | Component / API | Test Idea |
|----|--------|---------------------|-----------------|-----------|
| AC-01–04 | FR16, FR17 | §14 (AI Stack), §18.2 | `DocumentService`, `POST /documents` | Upload valid/oversized/scanned PDF; check parse_status |
| AC-05–08 | FR18 | §18.3 (pgvector) | `EmbeddingService`, `document_embeddings` | Assert chunk count matches expected; verify vector dimensions = 1536 |
| AC-09–11 | FR19–FR21 | §14.2 (GitHub) | `GitHubConnectorService`, `POST /github` | Connect with valid/invalid PAT; verify analysis_summary fields |
| AC-12–14 | FR22–FR25 | §14.2 (Playwright) | `DOMCrawlerService`, `POST /crawls` | Crawl public page; verify pages_crawled ≤ 100 |
| AC-15–16 | FR26–FR27 | §13 (E3 Agent Orchestrator) | `GET /agents`, agent selection UI | Verify 3 agents returned; pipeline created correctly |
| AC-17–18 | Budget (Arch §5) | §4.5 Token Budget | `TokenBudgetService`, Redis | Mock 100% budget; assert 429 returned |
| AC-19–21 | FR30 | §19.3 (SSE) | SSE endpoint `/events/agent-runs/{id}` | SSE event stream; parse events; verify completion event |
| AC-22–25 | FR32–FR35 | §13 (E3–E6) | `BAConsultantAgent`, `QAConsultantAgent`, `AutomationConsultantAgent` | Mock LLM; assert artifact_type, content structure |
| AC-26–29 | FR38–FR40 | §14.1 (Frontend) | `ArtifactService`, artifact viewer, Monaco editor | Create version; load diff; check content_type |
| AC-30–33 | FR67–FR71 | §13 (E11 Analytics) | `PMDashboardService`, Recharts dashboard | Mock artifacts; compute coverage %; assert trend data |
| AC-34–39 | FR78–FR81 | §13 (E9 JIRA) | `JIRAIntegrationService`, `jira_traceability` | Mock JIRA API; test connection; import flow; link artifact |
| AC-40 | Budget (Arch §5) | `GET /admin/token-usage` | `TokenBudgetService` | Assert cost calculation correct; verify alert threshold |

---

## 10. Risks, Assumptions & Open Questions

**Risk 1: LLM Cost Explosion** *(Pre-mortem score: CRITICAL)*
- **Scenario:** Token costs hit $5K/month for 50 tenants at enterprise tier
- **Mitigation:** Hard per-tenant token budgets (enforced pre-call); Redis 24h LLM response cache; prompt length optimization (context trimming before injection); real-time cost dashboard with 80% email alert

**Risk 2: LLM Latency & Output Quality** *(Risk score: 9)*
- **Scenario:** Agent pipeline takes > 20 minutes; generated test cases reference non-existent requirements
- **Mitigation:** Streaming SSE progress (eliminates blank wait); P95 < 10 minutes target; automated output validation (check generated tests reference real FRs from coverage matrix); 10 real PRDs tested pre-release

**Risk 3: JIRA Integration Brittleness** *(Pre-mortem score: 7)*
- **Scenario:** Atlassian API rate limit or version change breaks import silently
- **Mitigation:** DLQ with 5-retry / 24h exponential backoff; JIRA sync health dashboard (last sync time, error rate, status indicator); graceful degradation (show last-imported data if API down)

**Risk 4: Document Parsing Failures**
- **Scenario:** Scanned PDF (image-only) yields no text; complex table layouts parse incorrectly
- **Mitigation:** Parse failure shows actionable fallback message; Markdown upload promoted as preferred format; chunk preview shown for user verification

**Risk 5: GitHub Clone Storage Growth**
- **Scenario:** 100 tenants × 1GB average repo = 100GB temp storage on node disk
- **Mitigation:** 7-day auto-expiry enforced via arq scheduled job; shallow clone (`--depth=1`) limits download size; S3-backed clone storage evaluated for Phase 2

**Risk 6: Playwright DOM Crawl Resource Usage**
- **Scenario:** Concurrent crawl sessions per tenant spike CPU/memory on API pod
- **Mitigation:** 1 concurrent crawl per project limit (enforced at API layer); Playwright subprocess isolated; 30-minute hard timeout; K8s resource quota on agent pods

**Assumption A1:** OpenAI API access is provisioned and keys stored in AWS Secrets Manager by Epic 0 (Story 0-22).

**Assumption A2:** pgvector extension is available in the PostgreSQL 15+ instance provisioned in Epic 0 (Story 0-4). Enable via `CREATE EXTENSION vector;` in migration 013.

**Assumption A3:** Playwright Chromium binary is installed in the backend container image (add to Epic 0 Dockerfile: `playwright install chromium`).

**Assumption A4:** S3 bucket for document storage was created in Epic 0 (Story 0-22). Documents use existing `boto3` credential chain.

**Assumption A5:** JIRA instances are Atlassian Cloud (REST API v2/v3). On-premise JIRA Server is out of scope for MVP.

**Open Question Q1:** Should document embeddings be scoped to `project_id` or `tenant_id`? (Current design: project-scoped, allowing cross-document semantic search within a project only.)

**Open Question Q2:** What is the maximum context window injected into LLM agents? With 50-page PRD (~75K tokens), we may exceed GPT-4-turbo's context window. **Decision needed:** Use first N chunks (truncate), or semantic retrieval (vector search for most relevant chunks).

**Open Question Q3:** Should artifact content be stored in PostgreSQL (`TEXT`) or S3? Large Playwright script sets (89 files) could grow significantly. Current design: PostgreSQL for ≤ 1MB artifacts, S3 for larger.

---

## 11. Test Strategy

### Test Levels

| Level | Framework | Coverage Target | Notes |
|-------|-----------|-----------------|-------|
| Unit | `pytest` + `unittest.mock` | ≥ 90% line coverage for all services | Mock all external calls (OpenAI, JIRA, GitHub, S3) |
| Integration | `pytest` + `httpx.AsyncClient` | All API endpoints covered | Use existing mock-based pattern from Epic 1; no live DB/Redis required |
| Security | Manual + automated | OWASP Top 10 checks | Token injection tests; RBAC bypass attempts; encrypted credential leak checks |
| Performance | Locust / k6 | P95 targets per §6.1 | Parallel agent run load test (5 concurrent runs per tenant) |
| E2E (staging) | Playwright | Happy path per story | Document upload → agent run → artifact view (full flow) |

### Test Priorities

1. **TokenBudgetService** — Critical financial risk; test hard limit enforcement, Redis atomicity, 80% alert trigger
2. **AgentOrchestrator** — Mock LLM; verify context injection, error propagation, artifact creation
3. **EmbeddingService** — Verify chunk count, vector dimensions, token tracking
4. **JIRAIntegrationService** — Mock Atlassian API; test DLQ retry logic, encrypted key handling
5. **SSE endpoint** — Verify event order, connection lifecycle, reconnect behaviour
6. **DocumentService** — Test all 3 file formats; parse failure handling; size limit enforcement

### Test Data

- **PDF fixtures:** Valid 3-page PRD PDF; image-only (scanned) PDF; oversized (26MB) PDF
- **JIRA mock:** `responses` library mock for Atlassian REST API (success, 401, 429, 503)
- **LLM mock:** `unittest.mock.patch` on `LLMProviderService.complete()` → return deterministic JSON
- **GitHub mock:** `httpx_mock` for GitHub API; local bare git repo for clone test

### Story-Level AC Coverage

Each story's unit tests must cover all AC entries mapped to that story:
- 2-1: AC-01 through AC-04
- 2-2: AC-05 through AC-08
- 2-3: AC-09 through AC-10
- 2-4: AC-11
- 2-5: AC-12 through AC-14
- 2-6 through 2-7: AC-15 through AC-16
- 2-8 through 2-9: AC-17 through AC-21
- 2-10: AC-22 through AC-26
- 2-11: AC-27 through AC-29
- 2-12 through 2-14: AC-30 through AC-33
- 2-15: AC-34 through AC-35
- 2-16: AC-36 through AC-37
- 2-17: AC-38 through AC-39
- 2-18: AC-40

---

## Post-Review Follow-ups

*Added 2026-02-27 — Senior Developer Review of Story 2.1*

### Story 2.1 Action Items

- **[High]** Migration 013 is missing FK constraints (`REFERENCES … ON DELETE CASCADE`) for `document_chunks.document_id → documents.id`, `document_embeddings.chunk_id → document_chunks.id`, `documents.project_id → projects(id)`, and `documents.created_by → users(id)`. Must be fixed before Story 2-2 inserts real chunk/embedding data. [file: `backend/alembic/versions/013_enable_pgvector_and_create_documents.py`]
- **[Med]** `DocumentResponse` exposes `s3_key` to API clients — remove this field from the public schema. [file: `backend/src/api/v1/documents/schemas.py`]
- **[Med]** Replace `asyncio.create_task()` for audit fire-and-forget in `DocumentService` with a safer pattern (see Story 1.12 audit_service pattern for reference). [file: `backend/src/services/document_service.py`]
- **[Note]** BackgroundTasks durability: if server restarts mid-parse, parse job is lost. Acceptable for MVP; consider migrating to arq when Epic 2 scales up (Stories 2-6+).

### Story 2.2 Action Items

*Added 2026-02-27 — Senior Developer Review of Story 2.2*

- **[Med]** Add `test_parse_failure_on_openai_error` integration test — mock `_call_openai_embeddings` to raise, assert `parse_status='failed'` in DB. [file: `backend/tests/integration/test_document_embedding.py`]
- **[Low]** Fix redundant COUNT(*) in idempotency path of `generate_and_store` — capture `existing.scalar()` into a local variable and return it rather than issuing a second query. [file: `backend/src/services/embedding_service.py:115-135`]
- **[Low]** Remove or wire `_ADA_COST_PER_TOKEN` constant — currently defined but never used. [file: `backend/src/services/embedding_service.py:40`]
- **[Note]** Orphaned `document_chunks` on mid-batch OpenAI failure is a latent risk: partial rows are committed before failure, idempotency gate would skip re-embedding on retry. Add chunk cleanup in failure handler before migrating to arq retry (Stories 2-6+).

### Story 2.7 Action Items

*Added 2026-02-28 — Senior Developer Review of Story 2.7 (CHANGES REQUESTED)*

- **[Med]** Fix `_run_agent_step` — catch `BudgetExceededError` before re-raising and call `_update_step(status="failed", error_message=..., completed_at=now)` so the step does not remain stuck in `"running"` (AC-17d). [file: `backend/src/services/agents/orchestrator.py:199–202`]
- **[Med]** Add unit test `test_execute_pipeline_budget_exceeded_marks_step_failed` verifying the step UPDATE is called with `status="failed"` when `BudgetExceededError` occurs. [file: `backend/tests/unit/services/test_orchestrator.py`]
- **[Low]** Fix error message: `f"Agent {agent_type} failed after {_MAX_RETRIES} attempts"` — says "3 attempts" but loop runs 4 total iterations. Change to `"after {_MAX_RETRIES} retries"`. [file: `backend/src/services/agents/orchestrator.py:223`]
- **[Note]** AC-17f text in story + context.xml says `daily_budget=None` — contradicts constraint C10. Implementation is correct (uses 100_000). Update story AC-17f text to say `daily_budget=100_000` for clarity.

### Story 2.9 Action Items

*Added 2026-02-28 — Senior Developer Review of Story 2.9*

- **[Med]** `execute_pipeline()` failure paths (BudgetExceededError + generic Exception) do not emit a run-level SSE termination signal — client EventSource hangs indefinitely on failure. Fix: add `await sse_manager.publish(run_id, "complete", {"run_id": run_id, "all_done": True, "error": True})` in both except blocks after `await db.commit()`, wrapped in try/except for best-effort. [file: `backend/src/services/agents/orchestrator.py:507-542`]
- **[Med]** Frontend `all_done` handler navigates to Artifacts on any `all_done` event, including failure. Add check for `payload.error` to show an error banner instead. [file: `web/src/pages/projects/agents/AgentsTab.tsx:305-312`]
- **[Med]** Add integration test for pipeline-failure SSE termination path. [file: `backend/tests/integration/test_sse_events.py`]
- **[Low]** Wrap `JSON.parse(e.data)` in try/catch in `es.onmessage` to prevent silent crash on malformed SSE data. [file: `web/src/pages/projects/agents/AgentsTab.tsx:292`]
- **[Low]** Reset `activeAgents([])` in `es.onerror` handler to re-enable agent selection after stream error. [file: `web/src/pages/projects/agents/AgentsTab.tsx:320`]
- **[Note]** SSE endpoint path in tech-spec-epic-2.md §4.1 table is stale: `events/agents/{run_id}` should be `events/agent-runs/{run_id}`. Implementation and story spec are correct.
