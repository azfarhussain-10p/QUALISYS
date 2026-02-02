# QUALISYS AI Powered Testing Platform

**Project Brainstorm & Technical Specification**

---

## Table of Contents

- [Overview](#overview)
- [Target Audience](#target-audience)
- [Project Goals](#project-goals)
- [Core Product Features](#1-core-product-features-user-facing)
  - [Project & Role Features](#project--role-features)
  - [Ingestion & Understanding](#ingestion--understanding)
  - [Multi-Agent Capabilities](#multi-agent-capabilities)
  - [Test Artifacts & Execution](#test-artefacts--execution)
  - [Self-Healing & Maintenance](#self-healing--maintenance)
  - [Reporting & Dashboards](#reporting--dashboards)
  - [KPIs & SLA Monitoring](#kpis--sla-monitoring)
- [Architecture & Data Flow](#2-architecture--data-flow-high-level)
- [Tech Stack Recommendations](#3-tech-stack-recommendations)
- [Data Model & DB Choices](#4-data-model--db-choices-concise)
- [Artifact Workflow](#5-artifact--workflow-example-flow)
- [Self-Healing Approach](#6-self-healing-approach-practical)
- [LLM Hosting & Observability](#7-llm-hosting--observability-concise)
- [Security, Compliance & Governance](#8-security-compliance--governance)
- [Observability & Monitoring](#9-observability--monitoring)
- [Integrations & Ecosystem](#10-integrations--ecosystem)
- [Phased Roadmap](#11-phased-roadmap-mvp--enterprise)
- [Risks & Mitigations](#12-risks--mitigations)
- [Next Steps](#13-suggested-next-steps-actionable)
- [Quick Reference](#14-quick-reference--recommended-components)

---

## Overview

QUALISYS is an AI-powered testing platform designed to revolutionize the software testing lifecycle by combining document ingestion, DOM analysis, source code understanding, and multi-agent AI capabilities to produce comprehensive test artifacts and self-healing test automation.

## Target Audience

- **PM / CSM** (Project Managers / Customer Success Managers)
- **Manual Test Engineers**
- **Automation Engineers**
- **SRE/Platform Engineers**

## Project Goals

1. **Ingest** docs + app DOM + source code
2. **Produce** test artefacts
3. **Run tests** (manual + automated)
4. **Provide** dashboards, KPIs, SLAs, defect flows, and self-healing test automation

---

## 1) Core Product Features (User-Facing)

### Project & Role Features

- **Multi-tenant projects**: PM/CSM can create projects, invite/assign QA engineers, set roles, assign testing types and SLAs
- **RBAC / SSO**:
  - Roles: Owner/Admin, PM/CSM, QA-Manual, QA-Automation, Dev, Viewer
  - Support SSO (SAML/OAuth/OIDC) and optional Keycloak for on-prem
- **Project import**:
  - Upload PRD / SRS / RFP / spec docs
  - Provide an app URL
  - Connect to a GitHub repo (read-only token)

### Ingestion & Understanding

**Document Parsing** (LangChain-like flows):
- PDF, MS Word, Markdown, Confluence
- Emails, issue threads

**Source Code Reader**:
- Clone a branch (read-only)
- Parse repo, map routes/apis/components
- Collect manifests

**DOM Crawler/Scraper** (via Playwright):
- Site map, pages, forms
- Dynamic flows
- Cookies/auth flows

### Multi-Agent Capabilities

Specialized agents (user-selectable):

| Agent | Capability |
|-------|-----------|
| **Documentation Analyzer** | Requirements → coverage matrix |
| **Manual Tester** | Generate manual test checklists & exploratory prompts |
| **Automation Tester** | Generate Playwright/Puppeteer scripts |
| **Web Scraper** | Playwright-based DOM discovery and dynamic screenshots |
| **AI Log Reader / Summarizer** | Ingest logs, produce debug trails |
| **Test Case Generator** | BDD/Gherkin + negative cases + boundary analysis |
| **Security Scanner Orchestrator** | Invoke OWASP ZAP, Snyk, static code scanners |
| **Performance/Load Agent** | Invoke k6/Locust scenarios |

**Agent Selection UI**: Let user pick one or orchestrate a pipeline of agents

### Test Artefacts & Execution

**Generate**:
- Test Plans
- Test Suites
- Test Cases (manual + automated)
- BDD scenarios
- Test Execution Plans

**Playwright/Puppeteer Script Generation**:
- Smart locators
- Selectable browsers

**Test Runner Infrastructure**:
- Parallel execution
- Cross-browser (Chromium/Firefox/WebKit)
- Headless/headful options
- Support load/perf harnesses (k6, Locust)
- API/back-end tests (Postman/Newman, REST-assured)

**Manual Test Runner**:
- Checklist UI
- Capture evidence (screenshots/video)
- Link defects

**Automation Execution Pool**:
- Containers (Playwright Docker)
- Autoscaling runner pools

### Self-Healing & Maintenance

**Locator Fallback Strategies**:
- CSS/XPath + ML-suggested robust selector
- Text anchors, accessibility labels, visual anchors

**DOM-Change Detection**:
- Store fingerprints of pages
- On failure propose patched selectors and rerun tests

**Versioned Test Artifacts**:
- Audit trail of automatic fixes
- PM must approve on prod

### Reporting & Dashboards

**PM/CSM Dashboard**:
- Project health
- Test coverage
- Test execution velocity
- P1/P2 leakage
- SLA compliance
- Cost per test/story point

**QA Dashboard**:
- Current runs
- Flaky tests
- Failing suites
- Environment status

**Reporting Features**:
- Exportable PDF reports
- Scheduled email summaries
- Slack/MS Teams notifications

**Integrations**:
- Jira (create defects)
- TestRail/Testworthy
- GitHub (PR comments)
- Slack/MS Teams

### KPIs & SLA Monitoring

**Tracked Metrics**:
- Requirement coverage %
- Defect rejection %
- Test-case effectiveness
- Avg defect closure time
- P1/P2 leakage
- Number of tests executed
- Manual vs automated %
- Cost per test
- Test execution time
- Test release time
- Environment availability

**Auto-alerts** for breached SLAs (e.g., P1 leakage > threshold)

---

## 2) Architecture & Data Flow (High-Level)

### Ingest Layer
- Doc parsers (PDF/Office → text → pipeline)
- Git connector (read-only repo clone)
- Playwright crawler for DOM snapshots

### Processing Layer (Agents)
- Orchestrator (queue/worker) that dispatches tasks to specialized agents
- Agent runtime (Python/Node microservices); agents call LLMs, vector DBs, and tools

### Vector + Metadata Store
- **Vector DB**: Qdrant / Milvus / Weaviate / Pinecone
- Store: embeddings + metadata + doc location + snapshots

### Relational Store
- **PostgreSQL** for users, projects, permissions, artefacts metadata

### Test Execution Layer
- Containerized runner pool (K8s) hosting Playwright/Puppeteer workers
- Use a message queue to distribute runs

### Results & Reporting
- Time-series DB (Prometheus / Timescale) for metrics
- Grafana dashboards
- ELK for logs

### Model Serving
- Local LLM serving (Ollama for dev; vLLM or Ray/vLLM for production)
- Embedding model (sentence-transformers) for offline embedding

### Observability
- LLM observability (LangFuse / OpenTelemetry traces)
- System traces and infra monitoring

### Integrations
- Jira, TestRail/Testworthy, GitHub, Slack, Email, SSO providers

---

## 3) Tech Stack Recommendations

### Frontend
- **Framework**: React + TypeScript
- **Meta-framework**: Next.js (or Vite) for UI and server-rendered pages
- **Styling**: Tailwind + shadcn/ui (clean modern)
- **Charts**: Recharts for dashboards
- **Real-time**: WebSocket/Server-Sent Events for real-time run updates

### Backend & Agents
- **Python (FastAPI)** for agent orchestration + LangChain-like pipelines
- **LangChain** for rapid doc→agent templates
- **Node.js (NestJS)** optionally for integrations or if team prefers JS
- **Worker framework**: Celery / RQ / RabbitMQ for job distribution OR use Kafka for scale

### Storage

#### Relational DB
- **Production**: PostgreSQL (recommended)
- **Prototype**: SQLite (single-user mode only)

#### Vector DB
- **On-prem**: Qdrant or Weaviate or Milvus
- **Managed cloud**: Pinecone
- **Recommendation**: Qdrant is easy to self-host

#### Cache
- **Redis** for session, short-term caches, locks

#### Object Storage
- **On-prem**: MinIO
- **Cloud**: S3-compatible storage for screenshots, artifacts

### LLM & Embeddings

#### Embeddings
- sentence-transformers (local) or OpenSearch/Hub models

#### Local LLM Options

| Option | Use Case | Notes |
|--------|----------|-------|
| **Ollama** | Easy local dev hosting | Developer-friendly |
| **vLLM** | Production throughput | Better for production with GPU memory management; recommended for high concurrency and latency guarantees. Recent benchmarks indicate vLLM outperforms Ollama for high-throughput production scenarios |
| **Llama 3.1 family** | Meta models for higher capability | Be mindful of license/usage |

#### Recommended LLM Strategy

**Use Llama 3.1** (or newer Llama 3.x models) as the primary production-safe model for:
- Documentation analysis
- Reasoning
- Workflow evaluation
- System-wide insights

**Use a separate code-specialized model** such as:
- Mistral Codestral
- Code Llama

For:
- Generating Playwright automation
- E2E test scripts
- Other code-heavy artifacts

#### Why Llama 3.1 + Codestral/Code Llama?
- Strong reasoning reliability
- Safer output profiles
- Industry validation and mature ecosystem
- Better guardrails and alignment for enterprise testing workflows

#### Guardrails You Should Enforce
- Run all generated code through **Semgrep**, **Snyk**, or **Bandit**
- Sandbox all automation runs
- Require human approval before merging generated tests
- Use **LangFuse** or similar observability tooling

### Test Execution & Tools

- **E2E**: Playwright (primary) + option for Puppeteer for browser parity
- **Load/Perf**: k6 or Locust
- **Security**: OWASP ZAP, Snyk (code and dependency scanning)
- **API Testing**: Postman/Newman, or integrate with REST-assured for Java users
- **Reporting**: PDF generation libraries (WeasyPrint or wkhtmltopdf) for exportable reports

### Infra & Orchestration

- **Kubernetes** for production (autoscale runner pools, model-serving pods)
- **GPU scheduling** for model-serving nodes (NVIDIA A100/H100 if hosting Llama 3.1/large models)
- **CI/CD**: GitHub Actions / GitLab CI. Deploy via Helm charts
- **Secrets**: HashiCorp Vault or cloud KMS

---

## 4) Data Model / DB Choices (Concise)

| Database | Purpose |
|----------|---------|
| **Postgres** | Users, projects, roles, test metadata, executions, KPIs |
| **Vector DB** | Docs embeddings, DOM snapshots, code embeddings, test-step embeddings |
| **Object Store** | Screenshots, recordings, reports |
| **Redis** | Ephemeral locking, runner allocation |
| **Timeseries** | Prometheus / Timescale for metrics |

**Prototype**: SQLite + Qdrant + MinIO is fine

**Production**: Move to Postgres + Qdrant/Milvus + S3 + K8s + vLLM

---

## 5) Artifact / Workflow (Example Flow)

1. User creates project → uploads docs / links repo / provides URL
2. Ingest pipeline parses docs → stores text + metadata → creates embeddings in vector DB
3. DOM crawler (Playwright) takes snapshots, records workflows (logins can be provided as secure secrets)
4. Documentation Analyzer builds requirement-to-feature mapping and produces a coverage matrix
5. Test Case Generator creates manual & automated cases (+ BDD) and test suites
6. PM assigns tests → triggers execution (manual checklist or automated runner)
7. Runner service picks up jobs, runs in containers, reports pass/fail, artifacts stored
8. Failures → agents propose self-heal fixes → if approved, patch tests, rerun
9. Defects auto-created in Jira/TestRail; KPIs updated
10. Periodic executive report (PDF) exported or scheduled

---

## 6) Self-Healing Approach (Practical)

### Strategy
1. Store multiple selectors per step:
   - Text-anchor
   - aria-labels
   - Relative xpath
   - Visual hash

2. On failure:
   - Compute candidate selectors from DOM snapshot
   - Present automated suggestion in triage

3. Auto-update test when threshold passes:
   - Example: >3 matching heuristics
   - Always provide a PR for human approval

4. Maintain a history to revert if the auto-fix causes regressions

---

## 7) LLM Hosting & Observability (Concise)

### Development
- Host models with **Ollama** (rapid dev)
- Local embedding models for search

### Production
- Use **vLLM** or a managed on-prem stack for:
  - Throughput
  - GPU multiplexing
  - P99 latency improvements
- Benchmarks show vLLM outperforms Ollama at scale

### Observability
- Add **LangFuse** (or similar) for:
  - Tracing prompts, outputs, cost, and tool usage
  - Safety & content filters
  - Prompt/response validation
- Especially important for:
  - Code-gen outputs
  - Security-related outputs
  - (Note: DeepSeek-R1 shows code-security anomalies — add extra review step)

---

## 8) Security, Compliance & Governance

### Auth & RBAC
- OAuth2/OIDC, SAML SSO
- Multi-tenant scopes

### Secrets & Keys
- HashiCorp Vault
- K8s secrets sealed
- Rotate keys routinely

### Encryption
- **In transit**: TLS
- **At rest**: AES-256

### PII Handling
- Auto-redaction
- Masking in logs
- Opt-in data retention

### Compliance
- ISO27001, SOC2 readiness
- GDPR data deletion flows

### Audit
- Immutable audit logs for all actions that change:
  - Tests
  - Auto-fixes
  - LLM prompts that led to code generation or defect filing

### Model Safety
- Restrict models used for code generation or security-sensitive recommendations
- Apply static analyzers to any generated code before usage

---

## 9) Observability & Monitoring

### Infrastructure
- **Prometheus + Grafana**
- **ELK** for logs

### LLM
- **LangFuse/OpenTelemetry** traces for:
  - Prompts
  - Tool calls
  - Retries and latencies
  - Capture: prompt + sanitized context + model chosen

### Runner/Tests
- Per-test telemetry (duration, flakiness, retries)
- Store in timeseries DB and visualize trends

### Alerting
- SLA breaches
- Runner pool exhaustion
- Rising flakiness

---

## 10) Integrations & Ecosystem

### Issue Tracking
- **Jira**: Create tickets with steps + artifacts
- **GitHub Issues**

### Test Management
- **TestRail, Testworthy**: Create testcases / sync results

### CI
- Integrate test runs into PR workflows
- Run smoke/regression on PR

### ChatOps
- **Slack/MS Teams**: Notifications, actionable messages (re-run, open issue)

### SRE
- **PagerDuty** for critical production P1 leakages

---

## 11) Phased Roadmap (MVP → Enterprise)

### MVP (6–10 weeks)

- Auth, Project creation, doc upload
- Doc parsing + vector store and basic QA coverage matrix
- Playwright crawler + DOM snapshot storage
- Basic Test Case Generator (manual checklists + simple Playwright templates)
- Simple runner (single-node Playwright Docker), reports, and Jira integration
- Basic dashboards: executed tests, pass/fail

### v1 (3–6 months)

- Multi-agent orchestration, BDD generator, parallel runners, cross-browser
- Self-healing proof-of-concept; automated defect filing
- Embedding-based search across docs and snapshots
- Basic model hosting (Ollama) + LLM observability (LangFuse)

### Enterprise (6–12 months)

- vLLM production model serving with GPU autoscaling
- Advanced observability, multi-region
- Full SLA enforcement and KPI dashboards
- Tenant isolation, SOC2/ISO compliance
- Advanced security testing integration
- Load/performance pipelines
- Full audit trail, cost tracking

---

## 12) Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| **Model hallucinations / unsafe code** | Add static analysis, code review checkpoints, restrict code-gen models for security tasks |
| **LLM infra cost & latency** | Start with Ollama for dev; for prod use vLLM or managed GPU clusters |
| **Data privacy / PII leaking** | Redact before storing, policy enforcement, retention rules |
| **Flaky UI tests** | Invest in robust locators, visual testing, isolation in test environments |
| **Scale of vector DB** | Choose an on-prem proven option (Qdrant/Milvus) when GDPR requires data residency |

---

## 13) Suggested Next Steps (Actionable)

### 1. Prototype (2–4 weeks)
- Doc ingest → vector DB → simple QA coverage + manual test generator + Playwright crawler storing DOM snapshots
- Use SQLite + Qdrant + Ollama (dev)

### 2. Runner POC
- Containerized Playwright runner with 5 parallel workers
- Integrate results into Postgres + basic dashboard

### 3. Select Vector DB
- Evaluate: Qdrant vs Milvus vs Weaviate
- Choose embed model (sentence-transformers)

### 4. LLM Plan
- Start with Ollama for dev
- Define migration plan to vLLM for production
  - GPU requirements
  - Ops team readiness

### 5. Security Plan
- Define SAST/DAST gating for generated code
- Plan for compliance audit scope

---

## 14) Quick Reference — Recommended Components

| Component | Technology |
|-----------|------------|
| **Frontend** | React + TypeScript + Next.js + Tailwind |
| **Backend/Agents** | Python FastAPI + LangChain-style pipelines |
| **Vector DB** | Qdrant or Weaviate (self-host) |
| **RDBMS** | PostgreSQL (prod), SQLite (proto) |
| **Cache** | Redis |
| **Object Storage** | MinIO / S3 |
| **LLM Hosting** | Ollama (dev) → vLLM/Ray (prod) + LangFuse for observability |
| **E2E** | Playwright (primary) + Puppeteer (optional) |
| **Load/Perf** | k6 / Locust |
| **Security** | OWASP ZAP + Snyk |
| **CI/CD** | GitHub Actions, Helm + Kubernetes |

---

## References

- [Red Hat Developer - vLLM Performance](https://developers.redhat.com/articles/2024/12/17/vllm-vs-ollama-comparing-llm-inference-engines)
- [Llama 3.1 - Meta AI](https://ai.meta.com/llama/)
- [LangFuse - LLM Observability](https://langfuse.com/)
- [TechRadar - DeepSeek-R1 Security Concerns](https://www.techradar.com/pro/security/deepseek-r1-ai-model-raises-serious-security-concerns-as-researchers-demonstrate-that-it-can-create-malware)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-30
**Status**: Project Brainstorm & Technical Specification
