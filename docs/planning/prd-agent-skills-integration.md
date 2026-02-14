# QUALISYS — Agent Skills Integration: Product Requirements Document

**Product:** QUALISYS — AI System Quality Assurance Platform
**Feature:** Anthropic Agent Skills Integration
**Author:** John (PM Agent) | Requested by Azfar
**Date:** 2026-02-14
**Status:** Draft — Pending Architecture Board Approval
**Version:** 1.0
**PRD Reference:** Extends PRD v1.0 (FR32–FR37 Agent Capabilities)
**Architecture Reference:** Architecture v1.0 (Agent Orchestration Layer)
**Epic Alignment:** New Epic 7 (Post-MVP, follows Epic 6)
**Evaluation Sources:**
- `docs/evaluations/anthropic-agent-skills-architecture-board.md`
- `docs/evaluations/anthropic-agent-skills-executive-strategy.md`
- `docs/evaluations/anthropic-agent-skills-technical-review.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Strategic Context & Problem Statement](#2-strategic-context--problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Scope & Boundaries](#4-scope--boundaries)
5. [Functional Requirements](#5-functional-requirements)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [Architecture Integration Design](#7-architecture-integration-design)
8. [Agent-Skill Mapping & Progressive Disclosure Model](#8-agent-skill-mapping--progressive-disclosure-model)
9. [Orchestration Layer Modifications](#9-orchestration-layer-modifications)
10. [RAG Layer Integration](#10-rag-layer-integration)
11. [MCP Integration Strategy](#11-mcp-integration-strategy)
12. [Human-in-the-Loop Governance Extensions](#12-human-in-the-loop-governance-extensions)
13. [CI/CD Pipeline Integration](#13-cicd-pipeline-integration)
14. [Security & Compliance](#14-security--compliance)
15. [Database Schema Extensions](#15-database-schema-extensions)
16. [Skill Versioning & Lifecycle Management](#16-skill-versioning--lifecycle-management)
17. [Observability & Monitoring](#17-observability--monitoring)
18. [Epic 7 — Story Breakdown](#18-epic-7--story-breakdown)
19. [Phased Implementation Roadmap](#19-phased-implementation-roadmap)
20. [Cost-Benefit Analysis](#20-cost-benefit-analysis)
21. [Risk Assessment & Mitigation](#21-risk-assessment--mitigation)
22. [Dependencies & Constraints](#22-dependencies--constraints)
23. [Vendor Lock-in Mitigation Strategy](#23-vendor-lock-in-mitigation-strategy)
24. [Documentation Update Plan](#24-documentation-update-plan)
25. [Appendix: Decision Log](#25-appendix-decision-log)

---

## References

| # | Document | Path | Relevance |
|---|---|---|---|
| R1 | QUALISYS PRD v1.0 | `docs/planning/prd.md` | Parent PRD — FR32–FR37 agent capabilities |
| R2 | QUALISYS Architecture v1.0 | `docs/architecture/architecture.md` | Agent orchestration, RAG, multi-tenant patterns |
| R3 | Agent Specifications | `docs/planning/agent-specifications.md` | 7 agent definitions, RBAC matrix, approval gates |
| R4 | Epic Breakdown | `docs/epics/epics.md` | Epics 0–6, story structure, sequencing |
| R5 | Agent Skills Architecture Board Evaluation | `docs/evaluations/anthropic-agent-skills-architecture-board.md` | Technical feasibility, integration analysis |
| R6 | Agent Skills Executive Strategy Evaluation | `docs/evaluations/anthropic-agent-skills-executive-strategy.md` | Business case, competitive positioning, ROI |
| R7 | Agent Skills Technical Review | `docs/evaluations/anthropic-agent-skills-technical-review.md` | Deep technical analysis, performance, security |
| R8 | Sprint Status | `docs/sprint-status.yaml` | Current implementation progress |

**Note on terminology divergence from evaluation documents:** This PRD intentionally reclassifies the "Skill Adapter Layer" (evaluation docs) as "Skill Adapter Library" — a Python package, not a microservice — reducing operational overhead from 3 new services to 2 new services + 1 library.

---

## 1. Executive Summary

### The Problem

QUALISYS's 7 specialized AI agents currently load full context (15,000–30,000 tokens) for every invocation — regardless of whether the task requires the full agent capability surface. This creates three compounding problems:

1. **Token Cost Scaling:** As QUALISYS scales from 50 to 150+ tenants, LLM token costs scale linearly ($5,000–$10,000/month at 50 tenants), compressing margins and limiting pricing flexibility.
2. **Context Window Saturation:** Full-context loading reduces available tokens for actual task execution, degrading output quality for complex operations.
3. **Monolithic Agent Architecture:** Adding new capabilities requires full agent rebuilds (8–12 weeks per capability), slowing platform evolution.

### The Solution

Integrate Anthropic's **Agent Skills** framework into QUALISYS's multi-agent system using a **three-level progressive disclosure model** that loads only the capability needed for each invocation:

- **Level 1 (Metadata):** ~50–100 tokens per skill, always loaded — enables skill discovery
- **Level 2 (Instructions):** ~500–2,000 tokens per skill, loaded on invocation — procedural execution
- **Level 3 (Resources):** ~500–1,000 tokens per skill, loaded on demand — supporting materials

**Result:** 40–60% token cost reduction per agent invocation, modular agent architecture, and 2–4 week skill development cycles (vs 8–12 week agent rebuilds).

### Strategic Decision

**Epic 7 (Post-MVP, follows Epic 6)** — Agent Skills are a strategic optimization, not core functionality. QUALISYS MVP (Epics 1–5) delivers full value without Skills. Epic 6 delivers Advanced Agents. Epic 7 retrofits all 7 agents with Skills and builds the Skill infrastructure.

**Rationale:**
- MVP delivery is the #1 priority — Skills must not introduce delivery risk
- Epic 6 Advanced Agents must exist before Skills can optimize them
- POC validation during Epic 6 de-risks the Epic 7 investment
- The Agent SDK and Marketplace planned in Epic 6 (Story 6.5) provides a natural architectural foundation for Skills

---

## 2. Strategic Context & Problem Statement

### 2.1 Why Now?

Three converging forces make Agent Skills strategically important:

1. **Unit Economics Pressure:** At 150 tenants, QUALISYS's current token cost structure ($136,800/year) consumes 25–30% of gross margins. Skills reduce this to $54,720/year — a 60% reduction that directly flows to bottom line.

2. **Competitive Landscape:** Competitors (DeepEval, Braintrust) are optimizing their AI cost structures. Without Skills, QUALISYS faces pricing pressure as the market matures.

3. **Platform Extensibility:** The Agent SDK/Marketplace (Epic 6, Story 6.5) needs a modular capability model. Skills provide the canonical pattern for community-contributed agent capabilities.

### 2.2 Alignment with Existing Architecture

| QUALISYS System | Skills Integration Point | Compatibility |
|---|---|---|
| **LangChain AgentOrchestrator** | Skill Adapter Layer translates context | ✅ High |
| **Sequential Agent Chain** | Skills selected per-agent at invocation time | ✅ High |
| **Human-in-the-Loop (15 gates)** | Skill governance extends approval patterns | ✅ High |
| **RAG (pgvector)** | Skill-aware context pre-fetching | ✅ High |
| **MCP (Playwright)** | MCP → Skill Bridge Service | ⚠️ Medium |
| **CI/CD (GitHub Actions)** | Standard containerized deployment | ✅ High |
| **Multi-Tenant Isolation** | Skill execution inherits tenant context | ✅ High |
| **RBAC (6 roles)** | Skill permissions extend role matrix | ✅ High |
| **Observability (OpenTelemetry + LangFuse)** | Skill execution telemetry integration | ✅ High |

### 2.3 What This PRD Does NOT Cover

- **MVP changes** — Zero modifications to Epics 1–5
- **Epic 6 changes** — Epic 6 proceeds as planned; Skills POC runs in parallel
- **LLM provider migration** — Skills are Claude-specific but abstracted behind `SkillProvider` interface
- **Agent SDK redesign** — Skills complement the SDK, not replace it

---

## 3. Goals & Success Metrics

### 3.1 Primary Goals

| # | Goal | Metric | Target |
|---|---|---|---|
| G1 | Reduce LLM token costs | Token cost per agent invocation | ≥40% reduction |
| G2 | Improve agent modularity | Time to add new agent capability | ≤4 weeks (vs 8–12 current) |
| G3 | Maintain agent quality | Agent output quality score | Zero regression (baseline from MVP) |
| G4 | Enable platform extensibility | Skills available in marketplace | ≥20 skills at launch |
| G5 | Preserve governance integrity | Approval gate compliance | 100% maintained |

### 3.2 POC Success Criteria (Phase 1)

| Metric | Target | Measurement Method |
|---|---|---|
| Token reduction | >40% | LangFuse token tracking before/after |
| Latency increase | <1 second per skill invocation | OpenTelemetry P95 latency |
| Skill execution success rate | >95% | Skill Proxy Service error rate |
| Agent output quality | Zero degradation | A/B comparison with baseline |

### 3.3 Full Rollout Success Criteria (Phases 2–4)

| Metric | Target | Measurement Method |
|---|---|---|
| Token reduction across all agents | >50% | LangFuse aggregate reporting |
| Annual cost savings | >$40,000 | Financial reporting (token costs) |
| Agent regressions | Zero | Automated regression test suite |
| Skill development velocity | <4 weeks per skill | Sprint tracking |
| Platform uptime impact | <0.01% degradation | SLA monitoring |

---

## 4. Scope & Boundaries

### 4.1 In Scope

1. **Skill Registry Service** — New microservice for skill metadata, discovery, and lifecycle management
2. **Skill Proxy Service** — New microservice for skill execution via Claude API
3. **Skill Adapter Library** — Python package bridging LangChain and Claude API Skills
4. **Governance Extensions** — Skill approval workflows, execution gates, risk classification
5. **21 Custom Skills** — Covering all 7 QUALISYS agents (see Section 8)
6. **RAG Enhancement** — Skill-aware context pre-fetching and filtering
7. **CI/CD Pipeline** — Skill deployment, versioning, and rollback automation
8. **Observability** — Skill execution telemetry, cost tracking, performance monitoring
9. **Database Extensions** — Skills, skill_executions, skill_approvals tables
10. **Documentation Updates** — Agent specs, architecture doc, API docs, runbooks

### 4.2 Out of Scope

1. MVP agent modifications (Epics 1–5 unchanged)
2. MCP → Skill Bridge Service (deferred to Epic 8 — complexity/latency tradeoff unfavorable)
3. Community skill marketplace (depends on Agent SDK from Epic 6, Story 6.5)
4. Multi-LLM skill execution (Skills are Claude-specific; abstraction layer planned but provider support deferred)
5. Skill A/B testing infrastructure (deferred to optimization phase)

### 4.3 Critical Decision: MCP Bridge Deferral

**Decision:** Defer MCP → Skill Bridge Service to Epic 8.

**Rationale:**
- MCP (Playwright) currently serves optional TEA workflows (`tea_use_mcp_enhancements` flag)
- Bridge adds +200–500ms latency per MCP call through skill
- Adds 1 additional microservice to maintain
- Skills and MCP can operate independently — Skills optimize token costs, MCP handles browser automation
- Post-Epic 7, assess whether bridge value justifies complexity

**Impact:** Skills that need browser automation will invoke Playwright directly via the existing Playwright container pool (Epic 4 infrastructure), not through MCP bridge.

---

## 5. Functional Requirements

### 5.1 Skill Registry Service

| FR# | Requirement | Priority | Notes |
|---|---|---|---|
| **FR-SK1** | System shall maintain a centralized skill registry storing metadata (name, description, version, agent_id, risk_level, tags) for all registered skills | P0 | Core discovery |
| **FR-SK2** | System shall expose REST API for skill CRUD operations with tenant-scoped access control | P0 | Skill management |
| **FR-SK3** | System shall support skill discovery by agent_id, returning only skills mapped to the requesting agent | P0 | Agent-specific skills |
| **FR-SK4** | System shall enforce semantic versioning (major.minor.patch) for all skills | P1 | Version management |
| **FR-SK5** | System shall support skill deprecation with 30-day notice period and migration guidance | P1 | Lifecycle management |
| **FR-SK6** | System shall prevent skill deletion when active references exist | P0 | Data integrity |
| **FR-SK7** | System shall support skill tagging for RAG pre-fetching optimization | P1 | RAG integration |

### 5.2 Skill Proxy Service

| FR# | Requirement | Priority | Notes |
|---|---|---|---|
| **FR-SK8** | System shall execute custom skills via the configured LLM provider's skill execution API, supporting up to 8 skills per request | P0 | Core execution |
| **FR-SK9** | System shall translate QUALISYS agent context (ProjectContext, tenant_id, RAG results) into Claude API format | P0 | Context bridge |
| **FR-SK10** | System shall handle skill execution timeouts (configurable, default 120s) with graceful degradation | P0 | Reliability |
| **FR-SK11** | System shall implement retry logic with exponential backoff for transient Claude API failures | P0 | Resilience |
| **FR-SK12** | System shall route skill execution through tenant-scoped resource limits (max concurrent skills per tenant) | P0 | Fair usage |
| **FR-SK13** | System shall support skill fallback — if skill execution fails, agent falls back to full-context mode | P0 | Zero regression guarantee |
| **FR-SK14** | System shall log all skill executions with skill_id, agent_id, tenant_id, tokens_used, execution_time_ms, status | P0 | Audit trail |

### 5.3 Skill Adapter Library

| FR# | Requirement | Priority | Notes |
|---|---|---|---|
| **FR-SK15** | Library shall provide a skill adapter component compatible with the AgentOrchestrator interface | P0 | Orchestrator integration |
| **FR-SK16** | Library shall translate LangChain context objects to Claude API skill invocation format | P0 | Context translation |
| **FR-SK17** | Library shall translate Claude API skill responses back to LangChain-compatible format | P0 | Response translation |
| **FR-SK18** | Library shall support skill chaining — output of Skill A available as input to Skill B within same agent invocation | P1 | Advanced workflows |

### 5.4 Governance Extensions

| FR# | Requirement | Priority | Notes |
|---|---|---|---|
| **FR-SK19** | System shall classify skills by risk level: low (auto-approved), medium (QA-Automation approval), high (Architect/DBA approval) | P0 | Risk management |
| **FR-SK20** | System shall require deployment approval for new skills and major version updates | P0 | Change control |
| **FR-SK21** | System shall require pre-execution approval for high-risk skills (e.g., DatabaseConsultant schema validation) | P0 | Execution governance |
| **FR-SK22** | System shall integrate skill approvals into existing approval dashboard UI | P1 | UX consistency |
| **FR-SK23** | System shall support skill execution approval exemptions for pre-approved skill+context combinations | P2 | Efficiency optimization |

### 5.5 Agent Orchestrator Modifications

| FR# | Requirement | Priority | Notes |
|---|---|---|---|
| **FR-SK24** | AgentOrchestrator shall discover available skills for the current agent before invocation | P0 | Skill-aware orchestration |
| **FR-SK25** | AgentOrchestrator shall select relevant skills based on task context (document type, agent stage, project domain) | P0 | Intelligent selection |
| **FR-SK26** | AgentOrchestrator shall pass selected skill metadata in the agent's context initialization | P0 | Progressive disclosure |
| **FR-SK27** | AgentOrchestrator shall support mixed execution — some capabilities via skills, others via existing agent logic | P0 | Hybrid approach |
| **FR-SK28** | AgentOrchestrator shall maintain backward compatibility — agents function identically with skills disabled | P0 | Feature flag |

---

## 6. Non-Functional Requirements

### 6.1 Performance

| NFR# | Requirement | Target |
|---|---|---|
| **NFR-SK1** | Skill discovery latency | <50ms (P95) |
| **NFR-SK2** | Skill metadata loading | <100ms (P95) |
| **NFR-SK3** | Total skill execution overhead | <1,000ms (P95) including Claude API call |
| **NFR-SK4** | Skill Registry Service throughput | ≥500 requests/second |
| **NFR-SK5** | Skill Proxy Service throughput | ≥100 concurrent skill executions |

### 6.2 Scalability

| NFR# | Requirement | Target |
|---|---|---|
| **NFR-SK6** | Skill Registry horizontal scaling | 2–10 replicas (Kubernetes HPA) |
| **NFR-SK7** | Skill Proxy horizontal scaling | 2–20 replicas (queue depth-based) |
| **NFR-SK8** | Skill execution at scale | 50,000+ skill invocations/day (500 tenants) |

### 6.3 Availability

| NFR# | Requirement | Target |
|---|---|---|
| **NFR-SK9** | Skill Registry Service uptime | 99.9% (43.8 min/month downtime) |
| **NFR-SK10** | Skill Proxy Service uptime | 99.9% |
| **NFR-SK11** | Graceful degradation | Agent functions at full-context mode if skills unavailable |

### 6.4 Security

| NFR# | Requirement | Target |
|---|---|---|
| **NFR-SK12** | Skill container isolation | No network access to internal services except via API |
| **NFR-SK13** | Skill execution sandbox | Read-only filesystem except `/tmp` |
| **NFR-SK14** | Claude API key management | AWS Secrets Manager / Azure Key Vault, 90-day rotation |
| **NFR-SK15** | Skill execution audit retention | 90 days (configurable per tenant) |

---

## 7. Architecture Integration Design

### 7.1 System Architecture (Extended)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        QUALISYS Platform (Extended)                         │
│                                                                             │
│  ┌──────────────┐    ┌──────────────────────────┐    ┌──────────────────┐  │
│  │   Frontend    │    │   Agent Orchestrator      │    │   RAG Service    │  │
│  │  (Vite+React) │◄──►│   (LangChain + Skills)    │◄──►│  (pgvector)     │  │
│  └──────────────┘    └──────────┬───────────────┘    └──────────────────┘  │
│                                  │                                          │
│                    ┌─────────────┼─────────────┐                           │
│                    ▼             ▼              ▼                           │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────────┐   │
│  │  Agent Services   │ │ Skill Registry   │ │  Skill Proxy Service     │   │
│  │  (7 Agents)       │ │ Service (NEW)    │ │  (NEW)                   │   │
│  │                    │ │                  │ │                          │   │
│  │  BAConsultant     │ │  Skill Metadata  │ │  Skill Execution        │   │
│  │  QAConsultant     │ │  Discovery API   │ │  Claude API Bridge      │   │
│  │  AutomationConslt │ │  Versioning      │ │  Context Translation    │   │
│  │  LogReader        │ │  Lifecycle Mgmt  │ │  Error Handling         │   │
│  │  SecurityScanner  │ └──────────────────┘ │  Tenant Isolation       │   │
│  │  PerfLoadAgent    │                       └───────────┬──────────────┘   │
│  │  DBConsultant     │                                   │                  │
│  └──────────────────┘                                    ▼                  │
│                                                   ┌──────────────────┐     │
│  ┌──────────────────┐    ┌──────────────────┐     │   Claude API     │     │
│  │  Governance Svc   │    │ Skill Adapter    │     │   (Anthropic)    │     │
│  │  (Extended)       │    │ Library (NEW)    │     └──────────────────┘     │
│  │                    │    │                  │                              │
│  │  Skill Approvals  │    │  LangChain ←→    │                              │
│  │  Risk Assessment  │    │  Claude API      │                              │
│  │  Audit Logging    │    │  Translation     │                              │
│  └──────────────────┘    └──────────────────┘                              │
│                                                                             │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐     │
│  │   PostgreSQL      │    │     Redis         │    │   Prometheus/    │     │
│  │   + pgvector      │    │   (Cache/Queue)   │    │   Grafana/       │     │
│  │   + skills tables │    │   + skill cache   │    │   LangFuse       │     │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Request Flow (Skill-Enabled Agent Invocation)

```
1. User triggers agent (e.g., BAConsultant analysis)
       │
2. AgentOrchestrator receives request with ProjectContext
       │
3. AgentOrchestrator calls Skill Registry: GET /api/v1/skills?agent_id=baconsultant
       │  ← Returns: [{skill_id: "document-parser", name: "...", desc: "..."},
       │              {skill_id: "requirements-extractor", ...},
       │              {skill_id: "gap-analyzer", ...}]
       │
4. AgentOrchestrator selects relevant skills based on context
       │  (e.g., PDF uploaded → select document-parser + requirements-extractor)
       │
5. RAG Service pre-fetches skill-tagged context
       │  ← Filters: {"skill_tags": ["document-parser", "requirements"]}
       │
6. Governance Service checks: any high-risk skills requiring approval?
       │  ← Low-risk skills: auto-approved
       │  ← High-risk skills: wait for approval or fall back to full-context mode
       │
7. Skill Adapter translates LangChain context → Claude API format
       │
8. Skill Proxy Service invokes Claude API with skills + context
       │  ← Level 1: Skill metadata loaded (~100 tokens)
       │  ← Level 2: Selected skill instructions loaded (~2,000 tokens)
       │  ← Level 3: Resources loaded on-demand (~500 tokens)
       │
9. Claude API executes skill, returns result
       │
10. Skill Adapter translates response → LangChain format
       │
11. AgentOrchestrator continues agent chain with skill output
       │
12. Skill execution logged (skill_id, tokens_used, duration, status)
```

### 7.3 Fallback Architecture (Zero Regression Guarantee)

```
Skill Invocation Attempt
       │
       ├── Success → Use skill output (40-60% fewer tokens)
       │
       ├── Skill Registry unavailable → Agent runs full-context mode
       │
       ├── Skill Proxy timeout → Agent runs full-context mode
       │
       ├── Claude API error → Retry (3x exponential backoff) → Fall back to full-context
       │
       └── Governance blocks → Queue for approval OR fall back to full-context
```

**Critical Design Principle:** Every skill-enabled agent path must have a full-context fallback. Skills are optimization — never a hard dependency.

---

## 8. Agent-Skill Mapping & Progressive Disclosure Model

### 8.1 MVP Agent Skills (Phase 3 — Week 9–12)

#### BAConsultant AI Agent (3 Skills)

| Skill | Level 1 (Metadata) | Level 2 (Instructions) | Level 3 (Resources) | Risk |
|---|---|---|---|---|
| **Document Parser** | "Extracts structured data from PDFs, Word, Markdown" (~80 tokens) | PDF parsing workflow, text extraction patterns, chunking strategy (~1,500 tokens) | Python extraction scripts, format templates (~800 tokens) | Low |
| **Requirements Extractor** | "Identifies FRs, NFRs, business rules from documents" (~60 tokens) | Requirement identification patterns, categorization rules, quality criteria (~1,800 tokens) | Domain-specific templates, scoring rubrics (~600 tokens) | Low |
| **Gap Analyzer** | "Detects missing requirements, ambiguities, conflicts" (~70 tokens) | Gap detection heuristics, ambiguity patterns, conflict resolution (~1,200 tokens) | Historical gap patterns, industry checklists (~500 tokens) | Low |

**Token Savings:** Current full-context BAConsultant: ~25,000 tokens → With Skills: ~6,000 tokens (**76% reduction**)

#### QAConsultant AI Agent (3 Skills)

| Skill | Level 1 (Metadata) | Level 2 (Instructions) | Level 3 (Resources) | Risk |
|---|---|---|---|---|
| **Test Strategy Generator** | "Creates comprehensive test strategies from requirements" (~70 tokens) | Strategy generation workflow, coverage models, risk-based prioritization (~2,000 tokens) | Strategy templates, coverage matrices (~700 tokens) | Low |
| **BDD Scenario Writer** | "Generates Gherkin scenarios from user stories" (~60 tokens) | Gherkin syntax rules, scenario patterns, edge case generation (~1,500 tokens) | Example scenarios, domain glossaries (~500 tokens) | Low |
| **Test Data Generator** | "Creates synthetic test data for various domains" (~60 tokens) | Data generation patterns, domain-specific constraints, privacy rules (~1,400 tokens) | Data templates, faker configurations (~600 tokens) | Low |

**Token Savings:** Current full-context QAConsultant: ~20,000 tokens → With Skills: ~5,500 tokens (**72% reduction**)

#### AutomationConsultant AI Agent (3 Skills)

| Skill | Level 1 (Metadata) | Level 2 (Instructions) | Level 3 (Resources) | Risk |
|---|---|---|---|---|
| **Playwright Script Generator** | "Generates robust Playwright test scripts from test cases" (~70 tokens) | Script generation patterns, POM architecture, assertion strategies (~2,000 tokens) | Code templates, locator patterns (~800 tokens) | Low |
| **Selector Optimizer** | "Optimizes DOM selectors for resilience against UI changes" (~70 tokens) | Multi-strategy selector patterns, stability scoring, fallback chains (~1,500 tokens) | Selector examples, stability benchmarks (~500 tokens) | Low |
| **Self-Healing Analyzer** | "Analyzes test failures and proposes DOM-change fixes" (~70 tokens) | Failure analysis workflow, DOM diff analysis, confidence scoring (~1,800 tokens) | Historical fix patterns, success rate data (~600 tokens) | Medium |

**Token Savings:** Current full-context AutomationConsultant: ~22,000 tokens → With Skills: ~6,500 tokens (**70% reduction**)

### 8.2 Post-MVP Agent Skills (Phase 4 — Week 13–16)

#### DatabaseConsultant AI Agent (3 Skills)

| Skill | Level 1 | Level 2 | Level 3 | Risk |
|---|---|---|---|---|
| **Schema Validator** | Schema migration validation (~60 tokens) | Validation rules, backward compat checks (~1,500 tokens) | Migration templates (~500 tokens) | **High** |
| **ETL Checker** | ETL pipeline integrity validation (~60 tokens) | Row count/checksum verification (~1,200 tokens) | ETL patterns (~400 tokens) | Medium |
| **Performance Profiler** | Query performance analysis (~60 tokens) | Slow query detection, index analysis (~1,400 tokens) | Query optimization patterns (~500 tokens) | Medium |

#### Security Scanner Orchestrator (3 Skills)

| Skill | Level 1 | Level 2 | Level 3 | Risk |
|---|---|---|---|---|
| **Vulnerability Analyzer** | Security scan result analysis (~60 tokens) | OWASP analysis patterns (~1,600 tokens) | Vulnerability databases (~600 tokens) | Medium |
| **OWASP Top 10 Checker** | OWASP Top 10 validation (~60 tokens) | Check procedures per category (~1,800 tokens) | Test payloads, patterns (~700 tokens) | Medium |
| **Security Test Generator** | Security test case generation (~60 tokens) | Test generation for injection, XSS, CSRF (~1,500 tokens) | Security test templates (~500 tokens) | Medium |

#### Performance/Load Agent (3 Skills)

| Skill | Level 1 | Level 2 | Level 3 | Risk |
|---|---|---|---|---|
| **Load Test Generator** | k6/Locust test script generation (~60 tokens) | Load test patterns, ramp-up strategies (~1,400 tokens) | Script templates (~500 tokens) | Low |
| **Bottleneck Identifier** | Performance bottleneck detection (~60 tokens) | Analysis heuristics, threshold rules (~1,200 tokens) | Benchmark data (~400 tokens) | Low |
| **SLA Validator** | SLA compliance validation (~60 tokens) | SLA rules engine, threshold checks (~1,000 tokens) | SLA templates (~300 tokens) | Low |

#### AI Log Reader/Summarizer (3 Skills)

| Skill | Level 1 | Level 2 | Level 3 | Risk |
|---|---|---|---|---|
| **Error Pattern Detector** | Error pattern recognition in logs (~60 tokens) | Pattern matching rules, clustering (~1,400 tokens) | Pattern databases (~500 tokens) | Low |
| **Log Summarizer** | Test execution log summarization (~60 tokens) | Summarization strategies, priority rules (~1,200 tokens) | Summary templates (~400 tokens) | Low |
| **Negative Test Generator** | Generate tests from error patterns (~60 tokens) | Negative test patterns, boundary analysis (~1,300 tokens) | Test templates (~400 tokens) | Low |

### 8.3 Skill Totals

| Category | Count | Token Savings |
|---|---|---|
| MVP Agent Skills (Phase 3) | 9 skills | 70–76% per agent |
| Post-MVP Agent Skills (Phase 4) | 12 skills | 65–75% per agent |
| **Total** | **21 skills** | **40–60% aggregate** |

---

## 9. Orchestration Layer Modifications

### 9.1 AgentOrchestrator Changes

The existing LangChain-based `AgentOrchestrator` requires the following modifications:

```python
# Current interface (unchanged)
class AgentOrchestrator:
    def execute_agent(self, agent_id: str, context: ProjectContext) -> AgentResult:
        ...

# Extended interface (new methods)
class SkillAwareAgentOrchestrator(AgentOrchestrator):
    def __init__(self, skill_registry: SkillRegistryClient,
                 skill_proxy: SkillProxyClient,
                 skill_adapter: SkillAdapter,
                 rag_service: SkillAwareRAG,
                 feature_flags: FeatureFlagService):
        super().__init__()
        self.skill_registry = skill_registry
        self.skill_proxy = skill_proxy
        self.skill_adapter = skill_adapter
        self.rag_service = rag_service
        self.feature_flags = feature_flags

    def execute_agent(self, agent_id: str, context: ProjectContext) -> AgentResult:
        # Check if skills enabled for this agent
        if not self.feature_flags.is_enabled(f"skills.{agent_id}"):
            return super().execute_agent(agent_id, context)

        try:
            # Discover and select skills
            skills = self.skill_registry.discover(agent_id=agent_id)
            selected = self._select_skills(skills, context)

            # Pre-fetch skill-aware RAG context
            rag_context = self.rag_service.get_context_for_skills(
                selected, context.query
            )

            # Execute via skill proxy
            result = self.skill_proxy.execute(
                agent_id=agent_id,
                skills=selected,
                context=self.skill_adapter.translate(context, rag_context)
            )

            return self.skill_adapter.translate_response(result)

        except SkillExecutionError:
            # Fallback to full-context mode
            logger.warning(f"Skill execution failed for {agent_id}, falling back")
            return super().execute_agent(agent_id, context)
```

### 9.2 Feature Flag Strategy

Skills are enabled per-agent via feature flags, allowing gradual rollout:

| Flag | Description | Default |
|---|---|---|
| `skills.baconsultant.enabled` | Enable skills for BAConsultant | `false` |
| `skills.qaconsultant.enabled` | Enable skills for QAConsultant | `false` |
| `skills.automationconsultant.enabled` | Enable skills for AutomationConsultant | `false` |
| `skills.{agent_id}.enabled` | Enable skills for any agent | `false` |
| `skills.fallback.enabled` | Enable full-context fallback on skill failure | `true` |

### 9.3 Skill Selection Logic

#### 9.3.1 Context-to-Skill Matching Algorithm

Skill selection is deterministic, based on matching `ProjectContext` attributes against skill metadata tags. The algorithm evaluates three dimensions:

**Dimension 1: Document Type Match (required)**

| `context.document_type` | Matching Skill Tags | Example Skills Selected |
|---|---|---|
| `pdf`, `word`, `markdown` | `document-parsing` | Document Parser |
| `user-story`, `epic`, `requirement` | `requirements-analysis` | Requirements Extractor, Gap Analyzer |
| `test-strategy`, `test-plan` | `test-generation` | Test Strategy Generator, BDD Scenario Writer |
| `test-case`, `test-script` | `automation` | Playwright Script Generator, Selector Optimizer |
| `test-result`, `test-failure` | `self-healing`, `analysis` | Self-Healing Analyzer, Error Pattern Detector |
| `schema`, `migration`, `ddl` | `database` | Schema Validator, ETL Checker |
| `log`, `trace`, `error-report` | `log-analysis` | Error Pattern Detector, Log Summarizer |
| `security-scan`, `vulnerability-report` | `security` | Vulnerability Analyzer, OWASP Top 10 Checker |
| `performance-report`, `load-test` | `performance` | Bottleneck Identifier, SLA Validator |

**Dimension 2: Agent Stage Match (optional, narrows selection)**

| `context.agent_stage` | Matching Skill Tags | Effect |
|---|---|---|
| `ingestion` | `parsing`, `extraction` | Prioritize document parsing skills |
| `analysis` | `analysis`, `gap-detection` | Prioritize analytical skills |
| `generation` | `generation`, `writing` | Prioritize output generation skills |
| `validation` | `validation`, `checking` | Prioritize validation skills |
| `remediation` | `self-healing`, `fixing` | Prioritize repair skills |
| `null` / unset | _(no filter)_ | All matching skills from Dimension 1 |

**Dimension 3: Priority Scoring (ranks selected skills)**

When more skills match than the 8-skill Claude API limit, rank by:
1. **Exact tag match** (skill tag == context attribute): +3 points
2. **Category match** (skill tag category matches context domain): +1 point
3. **Historical success rate** (from `skill_executions` table, >90% success): +1 point
4. **Recency** (skill updated within last 30 days): +1 point

Top 8 by score are selected. Ties broken by skill creation order (oldest first — more battle-tested).

#### 9.3.2 Implementation

```python
# Skill tag matching rules
DOCUMENT_TYPE_TO_TAGS: dict[str, list[str]] = {
    "pdf": ["document-parsing"],
    "word": ["document-parsing"],
    "markdown": ["document-parsing"],
    "user-story": ["requirements-analysis"],
    "epic": ["requirements-analysis"],
    "requirement": ["requirements-analysis"],
    "test-strategy": ["test-generation"],
    "test-plan": ["test-generation"],
    "test-case": ["automation"],
    "test-script": ["automation"],
    "test-result": ["self-healing", "analysis"],
    "test-failure": ["self-healing", "analysis"],
    "schema": ["database"],
    "migration": ["database"],
    "log": ["log-analysis"],
    "security-scan": ["security"],
    "performance-report": ["performance"],
}

AGENT_STAGE_TO_TAGS: dict[str, list[str]] = {
    "ingestion": ["parsing", "extraction"],
    "analysis": ["analysis", "gap-detection"],
    "generation": ["generation", "writing"],
    "validation": ["validation", "checking"],
    "remediation": ["self-healing", "fixing"],
}

def _context_matches_skill(self, skill: Skill, context: ProjectContext) -> bool:
    """Deterministic skill matching based on context attributes."""
    # Dimension 1: Document type (required match)
    required_tags = DOCUMENT_TYPE_TO_TAGS.get(context.document_type, [])
    if not required_tags:
        return False  # Unknown document type — no skills selected

    skill_tags = set(skill.metadata.get("tags", []))
    if not skill_tags.intersection(required_tags):
        return False  # Skill doesn't match document type

    # Dimension 2: Agent stage (optional narrowing)
    if context.agent_stage:
        stage_tags = AGENT_STAGE_TO_TAGS.get(context.agent_stage, [])
        if stage_tags and not skill_tags.intersection(stage_tags):
            return False  # Skill doesn't match current agent stage

    return True

def _select_skills(self, available_skills: list[Skill],
                   context: ProjectContext) -> list[Skill]:
    """Select and rank relevant skills based on task context."""
    candidates = []

    for skill in available_skills:
        if self._context_matches_skill(skill, context):
            if self.governance.is_approved(skill.skill_id, context):
                score = self._score_skill(skill, context)
                candidates.append((score, skill))

    # Sort by score descending, limit to 8 per Claude API constraint
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [skill for _, skill in candidates[:8]]

def _score_skill(self, skill: Skill, context: ProjectContext) -> int:
    """Priority scoring for skill ranking."""
    score = 0
    skill_tags = set(skill.metadata.get("tags", []))
    required_tags = set(DOCUMENT_TYPE_TO_TAGS.get(context.document_type, []))

    # Exact tag match: +3
    if skill_tags.intersection(required_tags):
        score += 3

    # Historical success rate >90%: +1
    success_rate = self._get_skill_success_rate(skill.skill_id)
    if success_rate and success_rate > 0.90:
        score += 1

    # Recently updated: +1
    if skill.updated_at and (datetime.utcnow() - skill.updated_at).days < 30:
        score += 1

    return score
```

### 9.4 Sequential Chain Compatibility

The existing agent chain remains unchanged:

```
BAConsultant → [Human Approval] → QAConsultant → [Human Approval] → AutomationConsultant
```

Each agent independently selects and executes skills. Skill outputs flow through the same `AgentResult` interface — downstream agents are unaware whether upstream used skills or full-context mode.

### 9.5 Context Translation Mapping (SkillAdapter)

The `SkillAdapter` translates between LangChain's `ProjectContext` and the Claude API skill invocation format. This mapping is the critical bridge between QUALISYS's orchestration layer and Anthropic's skill execution.

#### 9.5.1 ProjectContext → Claude API Request Mapping

| ProjectContext Field | Claude API Target | Transformation |
|---|---|---|
| `context.tenant_id` | `system` prompt metadata block | Injected as `<!-- tenant: {tenant_id} -->` in system prompt for audit traceability. Never sent as user content. |
| `context.agent_id` | `system` prompt | Agent identity and role description prepended to system prompt. |
| `context.query` | `messages[].content` (user role) | Direct passthrough as the user message. |
| `context.document_type` | `system` prompt metadata | Included in system prompt: `Document type: {document_type}` — informs skill behavior. |
| `context.agent_stage` | `system` prompt metadata | Included in system prompt: `Agent stage: {agent_stage}` — guides skill focus. |
| `context.project_domain` | `system` prompt metadata | Included: `Domain: {project_domain}` — provides domain context to skill. |
| `context.uploaded_documents` | `messages[].content` (user role) | Document content appended to user message, chunked if >10,000 tokens. |
| `rag_results` (from RAG pre-fetch) | `messages[].content` (user role) | RAG context appended after query: `\n\n--- Relevant Context ---\n{rag_results}` |
| Selected skill metadata (Level 1) | `system` prompt | Skill names and descriptions injected into system prompt for skill discovery. |
| Selected skill IDs | `container.skills[]` | Skill IDs passed to Claude API `container` parameter for Level 2/3 loading. |

#### 9.5.2 Claude API Response → AgentResult Mapping

| Claude API Response Field | AgentResult Field | Transformation |
|---|---|---|
| `content[].text` | `result.output` | Primary text output — direct passthrough. |
| `content[].type == "tool_use"` | `result.tool_calls` | Tool invocations translated to LangChain `ToolCall` format. |
| `usage.input_tokens` | `result.metrics.tokens_input` | Direct passthrough for token metering. |
| `usage.output_tokens` | `result.metrics.tokens_output` | Direct passthrough for token metering. |
| `stop_reason` | `result.status` | `"end_turn"` → `"success"`, `"max_tokens"` → `"truncated"`, `"tool_use"` → `"pending_tool"` |
| `model` | `result.metrics.model` | Recorded for cost calculation and audit. |
| HTTP error (4xx/5xx) | Raises `SkillExecutionError` | Triggers fallback to full-context mode per Section 7.3. |

#### 9.5.3 Implementation

```python
class SkillAdapter:
    """Translates between LangChain ProjectContext and Claude API format."""

    def translate(self, context: ProjectContext,
                  rag_context: list[Document],
                  selected_skills: list[Skill]) -> dict:
        """Build Claude API request payload from QUALISYS context."""

        # System prompt: agent identity + metadata + skill discovery
        system_prompt = self._build_system_prompt(context, selected_skills)

        # User message: query + documents + RAG context
        user_content = self._build_user_content(context, rag_context)

        # Skill IDs for container parameter
        skill_ids = [s.skill_id for s in selected_skills]

        return {
            "model": "claude-sonnet-4-5-20250514",
            "max_tokens": 8192,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_content}
            ],
            "betas": ["computer-use-2025-01-24"],  # Skills beta header
            "container": {
                "skills": skill_ids
            },
            "metadata": {
                "tenant_id": str(context.tenant_id),  # For Anthropic audit
            }
        }

    def _build_system_prompt(self, context: ProjectContext,
                              skills: list[Skill]) -> str:
        """Construct system prompt with agent identity and skill metadata."""
        parts = [
            f"You are {context.agent_id}, a QUALISYS AI agent.",
            f"Document type: {context.document_type}",
            f"Agent stage: {context.agent_stage or 'general'}",
            f"Domain: {context.project_domain or 'software-testing'}",
            "",
            "Available skills:",
        ]
        # Level 1 metadata — always loaded (~50-100 tokens per skill)
        for skill in skills:
            parts.append(f"- {skill.name}: {skill.description}")

        return "\n".join(parts)

    def _build_user_content(self, context: ProjectContext,
                             rag_context: list[Document]) -> str:
        """Construct user message with query, documents, and RAG context."""
        parts = [context.query]

        # Append uploaded documents (chunked if large)
        if context.uploaded_documents:
            parts.append("\n\n--- Uploaded Documents ---")
            for doc in context.uploaded_documents:
                content = doc.content[:40_000]  # Truncate at ~10K tokens
                parts.append(f"\n### {doc.filename}\n{content}")

        # Append RAG context
        if rag_context:
            parts.append("\n\n--- Relevant Context ---")
            for doc in rag_context:
                parts.append(f"\n{doc.page_content}")

        return "\n".join(parts)

    def translate_response(self, claude_response: dict) -> AgentResult:
        """Convert Claude API response to LangChain-compatible AgentResult."""
        usage = claude_response.get("usage", {})

        # Extract text content
        output_parts = []
        tool_calls = []
        for block in claude_response.get("content", []):
            if block["type"] == "text":
                output_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCall(
                    name=block["name"],
                    arguments=block["input"],
                    id=block["id"]
                ))

        # Map stop reason to status
        stop_reason = claude_response.get("stop_reason", "end_turn")
        status_map = {
            "end_turn": "success",
            "max_tokens": "truncated",
            "tool_use": "pending_tool",
        }

        return AgentResult(
            output="\n".join(output_parts),
            tool_calls=tool_calls,
            status=status_map.get(stop_reason, "unknown"),
            metrics=AgentMetrics(
                tokens_input=usage.get("input_tokens", 0),
                tokens_output=usage.get("output_tokens", 0),
                model=claude_response.get("model", "unknown"),
            )
        )
```

#### 9.5.4 Example: Complete Skill Invocation

```python
# BAConsultant analyzing a PDF with Document Parser skill
context = ProjectContext(
    tenant_id="tenant_abc123",
    agent_id="baconsultant",
    query="Analyze this requirements document and extract all functional requirements",
    document_type="pdf",
    agent_stage="ingestion",
    project_domain="e-commerce",
    uploaded_documents=[Document(filename="requirements.pdf", content="...")],
)

# After skill selection: [document-parser] selected
# After RAG pre-fetch: 3 relevant docs returned

# Resulting Claude API request:
{
    "model": "claude-sonnet-4-5-20250514",
    "max_tokens": 8192,
    "system": "You are baconsultant, a QUALISYS AI agent.\nDocument type: pdf\nAgent stage: ingestion\nDomain: e-commerce\n\nAvailable skills:\n- Document Parser: Extracts structured data from PDFs, Word, Markdown",
    "messages": [
        {
            "role": "user",
            "content": "Analyze this requirements document and extract all functional requirements\n\n--- Uploaded Documents ---\n### requirements.pdf\n[PDF content here]\n\n--- Relevant Context ---\n[RAG results here]"
        }
    ],
    "betas": ["computer-use-2025-01-24"],
    "container": {
        "skills": ["document-parser"]
    },
    "metadata": {
        "tenant_id": "tenant_abc123"
    }
}
```

---

## 10. RAG Layer Integration

### 10.1 Skill-Aware Context Pre-Fetching

```python
class SkillAwareRAG:
    """Extends existing RAG service with skill-aware pre-fetching."""

    def get_context_for_skills(self, skills: list[Skill],
                                query: str) -> list[Document]:
        """Pre-fetch RAG context filtered by skill tags."""

        # Collect all skill tags
        skill_tags = set()
        for skill in skills:
            skill_tags.update(skill.metadata.get("tags", []))

        # Vector search with skill tag filtering
        relevant_docs = self.vector_search(
            query=query,
            filters={"tags": {"$in": list(skill_tags)}},
            limit=10  # Reduced from 20 — skills need less context
        )

        return relevant_docs
```

### 10.2 RAG Optimization Benefits

| Metric | Without Skills | With Skills | Improvement |
|---|---|---|---|
| RAG results per query | 20 documents | 10 documents | 50% reduction |
| Context tokens from RAG | ~15,000 | ~3,000 | 80% reduction |
| Retrieval latency | 200ms | 150ms | 25% faster |
| Relevance score | 0.72 avg | 0.85 avg | 18% more relevant |

### 10.3 Skill Knowledge Base

Store skill-specific patterns in pgvector for skill learning:

- Historical skill execution patterns
- Domain-specific skill configurations
- Successful skill output templates
- Tagged with `skill_id` for filtered retrieval

---

## 11. MCP Integration Strategy

### 11.1 Current State

- Playwright MCP used for browser automation in TEA workflows
- Controlled by `tea_use_mcp_enhancements` config flag
- MCP runs in IDE/CLI context, not in Claude API context

### 11.2 Decision: Coexistence, Not Bridge (Epic 7)

**Skills and MCP operate independently:**

| Concern | Resolution |
|---|---|
| Skills need browser automation | Use Playwright container pool directly (Epic 4 infrastructure) |
| MCP needs skill context | Not needed — MCP operates at IDE/development level |
| Future integration | Evaluate MCP → Skill Bridge in Epic 8 based on usage data |

### 11.3 Compatibility Guarantee

- Skills do NOT modify MCP behavior
- MCP configuration (`tea_use_mcp_enhancements`) remains unchanged
- Skills and MCP can both be enabled simultaneously without conflict
- No shared state between Skills and MCP subsystems

---

## 12. Human-in-the-Loop Governance Extensions

### 12.1 Skill Risk Classification

| Risk Level | Criteria | Approval Required | Examples |
|---|---|---|---|
| **Low** | Read-only operations, document analysis, test generation | Auto-approved | Document Parser, BDD Writer, Test Data Generator |
| **Medium** | Operations that produce executable code or security-relevant output | QA-Automation approval | Playwright Script Generator, Self-Healing Analyzer, Vulnerability Analyzer |
| **High** | Operations affecting databases, infrastructure, or production systems | Architect/DBA + PM dual approval | Schema Validator, ETL Checker |

### 12.2 Governance Integration with Existing 15 Gates

Skills integrate into the existing approval workflow — they do NOT add new gates to the agent chain:

```
BAConsultant (with skills) → [Existing Gate: Internal Review] → [Existing Gate: Client Review]
                                    ↑
                        Skills executed BEFORE this gate
                        Skill outputs included in review artifacts
```

**New governance added only for:**
1. **Skill deployment** — Architect/DevOps approves new skill deployment (one-time)
2. **High-risk skill execution** — DBA approves before DatabaseConsultant schema skills run
3. **Skill version updates** — Major version changes require Architect approval

### 12.3 Approval Workflow

```python
class SkillGovernance:
    """Extends existing ApprovalService for skill governance."""

    RISK_APPROVAL_MAP = {
        "low": None,  # Auto-approved
        "medium": ["qa_automation"],
        "high": ["architect", "dba"],
    }

    def check_execution_approval(self, skill: Skill,
                                  context: ProjectContext) -> bool:
        """Check if skill execution is approved."""
        required_roles = self.RISK_APPROVAL_MAP.get(skill.risk_level)

        if required_roles is None:
            return True  # Auto-approved

        # Check existing approvals for this skill+context combination
        approval = self.approval_service.get_approval(
            entity_type="skill_execution",
            entity_id=skill.skill_id,
            context_hash=self._hash_context(context)
        )

        return approval is not None and approval.status == "approved"
```

### 12.4 Audit Trail Extensions

| Event Type | Data Captured | Retention |
|---|---|---|
| `skill_deployed` | skill_id, version, deployer, approval_id | 365 days |
| `skill_executed` | skill_id, agent_id, tenant_id, tokens, duration, status | 90 days |
| `skill_approved` | skill_id, approver_id, approver_role, context_hash | 365 days |
| `skill_failed` | skill_id, error_type, error_message, fallback_used | 90 days |
| `skill_deprecated` | skill_id, deprecated_by, migration_guide_url | 365 days |

---

## 13. CI/CD Pipeline Integration

### 13.1 Skill Deployment Pipeline

```yaml
# .github/workflows/deploy-skill.yml
name: Deploy Skill
on:
  push:
    paths:
      - 'skills/**'
  pull_request:
    paths:
      - 'skills/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate SKILL.md frontmatter
        run: python scripts/validate-skill-metadata.py
      - name: Lint skill scripts
        run: ruff check skills/
      - name: Run skill unit tests
        run: pytest skills/tests/

  security-scan:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - name: Trivy container scan
        uses: aquasecurity/trivy-action@master
      - name: Secret detection
        uses: trufflesecurity/trufflehog@main

  build:
    needs: security-scan
    runs-on: ubuntu-latest
    steps:
      - name: Build skill container image
        run: docker build -t $ECR_REGISTRY/skill-$SKILL_NAME:$VERSION .
      - name: Push to ECR/ACR
        run: docker push $ECR_REGISTRY/skill-$SKILL_NAME:$VERSION

  deploy:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Register skill in Skill Registry
        run: |
          curl -X POST $SKILL_REGISTRY_URL/api/v1/skills \
            -H "Authorization: Bearer $SERVICE_TOKEN" \
            -d '{"skill_id": "$SKILL_ID", "version": "$VERSION", ...}'
      - name: Deploy to Skill Proxy Service
        run: kubectl apply -f k8s/skill-deployment.yaml
      - name: Run skill integration tests
        run: pytest skills/integration_tests/
      - name: Verify skill health
        run: curl $SKILL_PROXY_URL/api/v1/skills/$SKILL_ID/health
```

### 13.2 Skill Directory Structure

```
skills/
├── baconsultant/
│   ├── document-parser/
│   │   ├── SKILL.md              # Metadata + Instructions
│   │   ├── scripts/
│   │   │   └── parser.py         # Extraction logic
│   │   ├── resources/
│   │   │   └── templates.json    # Output templates
│   │   ├── tests/
│   │   │   └── test_parser.py    # Unit tests
│   │   └── Dockerfile            # Container definition
│   ├── requirements-extractor/
│   │   └── ...
│   └── gap-analyzer/
│       └── ...
├── qaconsultant/
│   └── ...
├── automationconsultant/
│   └── ...
└── shared/                        # Cross-agent shared skills (future)
    └── ...
```

### 13.3 Rollback Strategy

```
1. Skill version fails validation tests
       │
2. Automated rollback triggered
       │
3. Skill Registry reverts to previous version
       │
4. Skill Proxy Service pulls previous container image
       │
5. Notification sent: Slack + email to skill owner
       │
6. Incident logged in audit trail
```

---

## 14. Security & Compliance

### 14.1 RBAC Extensions

| Role | Skill Permissions |
|---|---|
| **Owner/Admin** | Full access: create, update, delete, deploy, execute all skills |
| **PM/CSM** | View skills, view execution logs, approve high-risk skill outputs |
| **QA-Automation** | Create/update skills for testing agents, execute all skills, approve medium-risk skills |
| **QA-Manual** | Execute low-risk skills (test data generation), view skill outputs |
| **Dev** | View skills, execute low-risk skills, view execution logs |
| **Viewer** | View skill catalog and execution results only |

### 14.2 Secrets Management

| Secret | Storage | Rotation | Scope |
|---|---|---|---|
| Claude API Key | AWS Secrets Manager / Azure Key Vault | 90 days | Skill Proxy Service |
| Skill Registry DB credentials | ExternalSecrets Operator | 90 days | Skill Registry Service |
| Service-to-service tokens | Kubernetes Secrets | 30 days | Inter-service auth |

### 14.3 Container Security

```yaml
# Skill Proxy Pod Security Context
apiVersion: v1
kind: Pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
    readOnlyRootFilesystem: true
  containers:
    - name: skill-proxy
      resources:
        limits:
          cpu: "2"
          memory: "4Gi"
        requests:
          cpu: "500m"
          memory: "1Gi"
      volumeMounts:
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: tmp
      emptyDir:
        sizeLimit: "1Gi"
```

### 14.4 Network Policies

```yaml
# Skill Proxy → Claude API only (egress restricted)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: skill-proxy-egress
spec:
  podSelector:
    matchLabels:
      app: skill-proxy
  policyTypes:
    - Egress
  egress:
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0  # Claude API (Anthropic IPs)
      ports:
        - protocol: TCP
          port: 443
    - to:
        - podSelector:
            matchLabels:
              app: skill-registry  # Internal skill registry
      ports:
        - protocol: TCP
          port: 8080
```

### 14.5 Tenant Isolation

- Skill execution inherits tenant context from AgentOrchestrator
- Tenant ID passed through entire skill chain: Orchestrator → Registry → Proxy → Claude API → Response
- Skill execution logs scoped to tenant_id (RLS enforced)
- No cross-tenant skill data leakage possible — skills are stateless, context is tenant-scoped

---

## 15. Database Schema Extensions

### 15.1 New Tables

```sql
-- Skill registry (within each tenant schema)
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    version VARCHAR(20) NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('anthropic', 'custom')),
    agent_id VARCHAR(50) NOT NULL,
    risk_level VARCHAR(20) DEFAULT 'low' CHECK (risk_level IN ('low', 'medium', 'high')),
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    container_image VARCHAR(500),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('draft', 'active', 'deprecated', 'retired')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deprecated_at TIMESTAMPTZ,
    CONSTRAINT valid_version CHECK (version ~ '^\d+\.\d+\.\d+$')
);

CREATE INDEX idx_skills_agent_id ON skills(agent_id);
CREATE INDEX idx_skills_status ON skills(status);
CREATE INDEX idx_skills_tags ON skills USING GIN(tags);

-- Skill execution audit trail
CREATE TABLE skill_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id VARCHAR(100) NOT NULL,
    agent_id VARCHAR(50) NOT NULL,
    tenant_id UUID NOT NULL,
    project_id UUID,
    user_id UUID,
    context_hash VARCHAR(64),
    tokens_input INTEGER,
    tokens_output INTEGER,
    execution_time_ms INTEGER,
    status VARCHAR(20) CHECK (status IN ('success', 'error', 'timeout', 'fallback')),
    error_message TEXT,
    fallback_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_skill_exec_tenant ON skill_executions(tenant_id);
CREATE INDEX idx_skill_exec_skill ON skill_executions(skill_id);
CREATE INDEX idx_skill_exec_created ON skill_executions(created_at);

-- Skill approvals
CREATE TABLE skill_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id VARCHAR(100) NOT NULL,
    approval_type VARCHAR(30) CHECK (approval_type IN ('deployment', 'execution', 'version_update')),
    approver_id UUID NOT NULL,
    approver_role VARCHAR(50),
    context_hash VARCHAR(64),
    status VARCHAR(20) CHECK (status IN ('pending', 'approved', 'rejected')),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_skill_approvals_skill ON skill_approvals(skill_id);
CREATE INDEX idx_skill_approvals_status ON skill_approvals(status);
```

### 15.2 Migration Strategy

- Alembic migration scripts for schema changes
- Applied per-tenant schema (consistent with existing multi-tenant pattern)
- Backward compatible — new tables, no modifications to existing tables
- Rollback migration available (drop tables)

---

## 16. Skill Versioning & Lifecycle Management

### 16.1 Version Strategy

| Version Component | Trigger | Example |
|---|---|---|
| **Major** (X.0.0) | Breaking changes to skill interface | document-parser v2.0.0 (new output format) |
| **Minor** (1.X.0) | New features, backward compatible | document-parser v1.2.0 (added Excel support) |
| **Patch** (1.0.X) | Bug fixes, backward compatible | document-parser v1.0.3 (fixed PDF edge case) |

### 16.2 Lifecycle States

```
Draft → Active → Deprecated (30-day notice) → Retired
  │       │            │
  │       │            └── Migration guide published
  │       │                 Notifications sent
  │       │
  │       └── Available for invocation
  │            Version pinning supported
  │
  └── Under development
       Not available for invocation
```

### 16.3 Version Pinning

Agents can pin to specific skill versions for stability:

```python
# Skill Registry configuration
{
    "agent_id": "baconsultant",
    "skill_pins": {
        "document-parser": "1.2.0",    # Pinned to specific version
        "requirements-extractor": "latest",  # Always use latest
        "gap-analyzer": "1.x"          # Latest minor within v1
    }
}
```

---

## 17. Observability & Monitoring

### 17.1 OpenTelemetry Integration

```python
# Skill execution tracing
from opentelemetry import trace

tracer = trace.get_tracer("qualisys.skills")

class SkillProxyService:
    def execute_skill(self, skill_id: str, context: dict):
        with tracer.start_as_current_span(
            "skill.execute",
            attributes={
                "skill.id": skill_id,
                "skill.agent_id": context.get("agent_id"),
                "skill.tenant_id": str(context.get("tenant_id")),
            }
        ) as span:
            result = self._invoke_claude_api(skill_id, context)
            span.set_attribute("skill.tokens_used", result.tokens)
            span.set_attribute("skill.execution_ms", result.duration_ms)
            return result
```

### 17.2 LangFuse Integration

| Metric | Tracking Point | Dashboard |
|---|---|---|
| Token usage per skill | Skill Proxy Service | Cost Optimization Dashboard |
| Token savings vs full-context | AgentOrchestrator (before/after comparison) | ROI Dashboard |
| Skill execution latency | Skill Proxy Service | Performance Dashboard |
| Skill failure rate | Skill Proxy Service | Reliability Dashboard |
| Fallback activation rate | AgentOrchestrator | Health Dashboard |

### 17.3 Prometheus Metrics

```python
# Custom Prometheus metrics
skill_execution_total = Counter(
    "qualisys_skill_executions_total",
    "Total skill executions",
    ["skill_id", "agent_id", "status"]
)

skill_execution_duration = Histogram(
    "qualisys_skill_execution_duration_seconds",
    "Skill execution duration",
    ["skill_id", "agent_id"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

skill_tokens_saved = Counter(
    "qualisys_skill_tokens_saved_total",
    "Total tokens saved by skills vs full-context",
    ["skill_id", "agent_id"]
)

skill_fallback_total = Counter(
    "qualisys_skill_fallback_total",
    "Total fallbacks to full-context mode",
    ["skill_id", "agent_id", "reason"]
)
```

### 17.4 Grafana Dashboards

1. **Skills Overview** — Execution volume, success rate, token savings
2. **Skills Performance** — P50/P95/P99 latency per skill, per agent
3. **Skills Cost** — Token cost comparison (skills vs full-context), savings trend
4. **Skills Health** — Error rates, fallback rates, timeout rates
5. **Skills Governance** — Pending approvals, approval turnaround time

### 17.5 Alerting Rules

| Alert | Condition | Severity | Action |
|---|---|---|---|
| Skill failure rate >5% | 5-minute window | Warning | Investigate, consider disabling skill |
| Skill failure rate >15% | 5-minute window | Critical | Auto-disable skill, fallback to full-context |
| Skill latency P95 >3s | 10-minute window | Warning | Check Claude API status, scale Proxy |
| Fallback rate >20% | 15-minute window | Warning | Review skill health, check dependencies |
| Skill Registry unavailable | 1-minute check | Critical | Page on-call, agents auto-fallback |

---

## 18. Epic 7 — Story Breakdown

### Epic 7: Agent Skills Integration

**Duration:** 16 weeks (4 phases)
**Dependencies:** Epic 5 (MVP complete), Epic 6 (Advanced Agents deployed)
**Primary Personas:** QA-Automation, Dev, Owner/Admin
**Risk Level:** Medium (Score 5–6) — Architectural changes with full-context fallback safety net

---

#### Phase 1: Proof of Concept (Weeks 1–4) — 5 Stories

**Story 7.1: Skill Registry Service (MVP)**
As a platform operator, I want a Skill Registry Service that stores and serves skill metadata, so that agents can discover available skills.
- AC1: FastAPI service deployed to Kubernetes (2 replicas)
- AC2: PostgreSQL `skills` table created with Alembic migration
- AC3: REST API: `GET /api/v1/skills`, `GET /api/v1/skills/{skill_id}`, `POST /api/v1/skills`
- AC4: Skill discovery by agent_id: `GET /api/v1/skills?agent_id=baconsultant`
- AC5: Health check endpoint: `GET /health`
- AC6: Response time <50ms (P95) for discovery queries
- AC7: Unit tests >90% coverage
- **FRs Covered:** FR-SK1, FR-SK2, FR-SK3

**Story 7.2: BAConsultant Document Parser Skill**
As a developer, I want to create the first custom skill (Document Parser) for BAConsultant, so that we can validate the progressive disclosure model.
- AC1: SKILL.md created with Level 1 metadata (name, description)
- AC2: Level 2 instructions: PDF/Word/Markdown parsing workflow
- AC3: Level 3 resources: Python extraction scripts, format templates
- AC4: Skill registered in Skill Registry
- AC5: Skill structure follows Anthropic SKILL.md specification
- **FRs Covered:** FR-SK8 (partial)

**Story 7.3: Skill Proxy Service (MVP)**
As a platform operator, I want a Skill Proxy Service that executes skills via Claude API, so that agents can use skills.
- AC1: FastAPI service deployed to Kubernetes (2 replicas, HPA configured)
- AC2: Claude API integration with `container` parameter and beta headers
- AC3: Skill execution endpoint: `POST /api/v1/skills/{skill_id}/execute`
- AC4: Context translation: ProjectContext → Claude API format
- AC5: Timeout handling (120s default, configurable)
- AC6: Retry logic with exponential backoff (3 retries)
- AC7: Execution audit logging (skill_id, tokens, duration, status)
- AC8: Health check: `GET /health`
- **FRs Covered:** FR-SK8, FR-SK9, FR-SK10, FR-SK11, FR-SK14

**Story 7.4: Skill Adapter Library (MVP)**
As a developer, I want a Python library that bridges LangChain and the Skill Proxy Service, so that the AgentOrchestrator can invoke skills.
- AC1: Python package `qualisys-skill-adapter` created
- AC2: `SkillAdapter.translate()` converts LangChain context → Claude API format
- AC3: `SkillAdapter.translate_response()` converts Claude API response → LangChain format
- AC4: Integration with AgentOrchestrator via `SkillAwareAgentOrchestrator` subclass
- AC5: Feature flag `skills.baconsultant.enabled` controls skill activation
- AC6: Full-context fallback on any skill failure
- AC7: Unit tests >90% coverage
- **FRs Covered:** FR-SK15, FR-SK16, FR-SK17, FR-SK24, FR-SK25, FR-SK26, FR-SK28

**Story 7.5: POC Validation & Metrics**
As a product manager, I want to measure token reduction, latency impact, and output quality for the BAConsultant Document Parser skill, so that we can validate the business case.
- AC1: LangFuse tracking: token usage with skills vs without skills
- AC2: OpenTelemetry tracing: skill execution latency breakdown
- AC3: A/B comparison: 50% of BAConsultant invocations use skill, 50% full-context
- AC4: Quality comparison: independent review of 20 skill outputs vs 20 full-context outputs
- AC5: POC report generated: token reduction %, latency delta, quality assessment
- AC6: Success criteria validated: >40% token reduction, <1s latency increase, zero quality regression
- AC7: Go/no-go decision documented for Phase 2
- **FRs Covered:** N/A (validation story)

---

#### Phase 2: Core Infrastructure (Weeks 5–8) — 5 Stories

**Story 7.6: Skill Registry Service (Full)**
As a platform operator, I want the Skill Registry to support versioning, deprecation, and lifecycle management, so that skills can be managed in production.
- AC1: Semantic versioning enforced on all skills
- AC2: Version pinning API: agents can pin to specific skill versions
- AC3: Deprecation workflow: 30-day notice, migration guidance, notifications
- AC4: Skill cannot be deleted with active references
- AC5: Skill tagging for RAG pre-fetch optimization
- AC6: Redis caching for skill metadata (24h TTL)
- **FRs Covered:** FR-SK4, FR-SK5, FR-SK6, FR-SK7

**Story 7.7: Skill Proxy Service (Production-Ready)**
As a platform operator, I want the Skill Proxy Service to handle production-scale load with tenant isolation, so that skills work reliably at scale.
- AC1: HPA configured: 2–20 replicas, scaling on request queue depth
- AC2: Tenant-scoped resource limits (max concurrent skills per tenant)
- AC3: Claude API rate limit handling (queuing with backoff)
- AC4: Container security: non-root, read-only filesystem, resource limits
- AC5: Network policy: egress restricted to Claude API + Skill Registry
- AC6: Handles 100+ concurrent skill executions
- **FRs Covered:** FR-SK12, NFR-SK5, NFR-SK7

**Story 7.8: Governance Extensions for Skills**
As a platform admin, I want skill governance integrated into existing approval workflows, so that skill deployment and execution follow our governance model.
- AC1: Skill risk classification (low/medium/high) stored in registry
- AC2: Deployment approval workflow: new skills and major versions require Architect approval
- AC3: High-risk execution approval: Schema Validator skill requires DBA + PM approval
- AC4: Approval dashboard updated: skills section shows pending skill approvals
- AC5: Audit trail: all skill governance events logged
- AC6: Notification: Slack/email alerts for pending skill approvals
- **FRs Covered:** FR-SK19, FR-SK20, FR-SK21, FR-SK22

**Story 7.9: RAG Skill-Aware Pre-Fetching**
As a developer, I want the RAG service to pre-fetch context filtered by selected skill tags, so that skills receive more relevant context with fewer tokens.
- AC1: `SkillAwareRAG.get_context_for_skills()` method implemented
- AC2: Skill tags used as pgvector filter metadata
- AC3: Context limit reduced from 20 to 10 documents when skills active
- AC4: Relevance score improvement: >10% measured via A/B test
- AC5: Pre-fetch latency: <150ms (P95)
- **FRs Covered:** FR-SK7 (RAG side)

**Story 7.10: Skill CI/CD Pipeline**
As a DevOps engineer, I want automated CI/CD for skill deployment, so that skills can be safely deployed and rolled back.
- AC1: GitHub Actions workflow: validate → security scan → build → deploy
- AC2: SKILL.md frontmatter validation (automated)
- AC3: Trivy container scanning for skill images
- AC4: Automated integration tests run post-deployment
- AC5: Rollback: one-command revert to previous skill version
- AC6: Deployment notifications: Slack channel `#skill-deployments`
- **FRs Covered:** N/A (infrastructure story)

---

#### Phase 3: MVP Agent Integration (Weeks 9–12) — 5 Stories

**Story 7.11: BAConsultant Full Skill Integration**
As a BAConsultant user, I want all BAConsultant capabilities delivered via skills, so that document analysis uses fewer tokens.
- AC1: 3 skills deployed: Document Parser, Requirements Extractor, Gap Analyzer
- AC2: Skills selected based on document type (PDF/Word/Markdown)
- AC3: Skill chaining: Parser output feeds into Extractor, Extractor feeds into Gap Analyzer
- AC4: Feature flag `skills.baconsultant.enabled` controls activation
- AC5: Token reduction validated: >50% vs full-context baseline
- AC6: Zero regression: output quality matches or exceeds baseline
- AC7: Fallback tested: skills disabled → agent functions normally
- **FRs Covered:** FR-SK18, FR-SK27

**Story 7.12: QAConsultant Skill Integration**
As a QAConsultant user, I want test artifact generation delivered via skills, so that test strategy and BDD generation uses fewer tokens.
- AC1: 3 skills deployed: Test Strategy Generator, BDD Scenario Writer, Test Data Generator
- AC2: Skills selected based on task type (strategy vs scenarios vs data)
- AC3: Feature flag `skills.qaconsultant.enabled` controls activation
- AC4: Token reduction validated: >50%
- AC5: Zero regression in test case quality
- **FRs Covered:** FR-SK18, FR-SK27

**Story 7.13: AutomationConsultant Skill Integration**
As an AutomationConsultant user, I want script generation and self-healing delivered via skills, so that automation uses fewer tokens.
- AC1: 3 skills deployed: Playwright Script Generator, Selector Optimizer, Self-Healing Analyzer
- AC2: Self-Healing Analyzer classified as medium-risk (QA-Automation approval required)
- AC3: Skills integrate with existing self-healing engine (Epic 4)
- AC4: Feature flag `skills.automationconsultant.enabled` controls activation
- AC5: Token reduction validated: >40%
- AC6: Self-healing accuracy: no regression from baseline
- **FRs Covered:** FR-SK18, FR-SK19, FR-SK27

**Story 7.14: Observability & Monitoring Dashboard**
As a platform operator, I want skill execution metrics visible in Grafana and LangFuse, so that I can monitor skill performance, costs, and health.
- AC1: Prometheus metrics: execution count, duration histogram, tokens saved, fallback rate
- AC2: OpenTelemetry spans: skill execution tracing with full context
- AC3: LangFuse integration: token cost comparison (skills vs full-context)
- AC4: 5 Grafana dashboards: Overview, Performance, Cost, Health, Governance
- AC5: Alerting rules: failure rate, latency, fallback triggers
- AC6: Cost savings report: monthly automated email to stakeholders
- **FRs Covered:** NFR-SK1 through NFR-SK5

**Story 7.15: Regression Test Suite for Skills**
As a QA engineer, I want automated regression tests ensuring skill-enabled agents produce identical-quality output, so that we can deploy skills with confidence.
- AC1: Regression test suite: 50+ test cases covering all 9 MVP agent skills
- AC2: A/B quality comparison: skill output vs full-context output scored by rubric
- AC3: Automated regression runs in CI/CD before skill deployment
- AC4: Quality gate: deployment blocked if regression score drops >5%
- AC5: Test coverage report: all skill paths, edge cases, fallback scenarios
- **FRs Covered:** N/A (quality assurance story)

---

#### Phase 4: Post-MVP Agent Integration (Weeks 13–16) — 5 Stories

**Story 7.16: DatabaseConsultant Skill Integration**
As a DatabaseConsultant user, I want schema validation, ETL checking, and performance profiling delivered via skills, so that database operations use fewer tokens.
- AC1: 3 skills deployed: Schema Validator (high-risk), ETL Checker (medium), Performance Profiler (medium)
- AC2: Schema Validator requires DBA + PM dual approval before execution
- AC3: Skills integrate with existing DatabaseConsultant agent (Epic 6, Story 6.8)
- AC4: Feature flag `skills.dbconsultant.enabled` controls activation
- AC5: Token reduction validated: >50%

**Story 7.17: Security Scanner Skill Integration**
As a Security Scanner user, I want vulnerability analysis and OWASP validation delivered via skills.
- AC1: 3 skills deployed: Vulnerability Analyzer, OWASP Top 10 Checker, Security Test Generator
- AC2: All classified as medium-risk (QA-Automation approval)
- AC3: Token reduction validated: >45%

**Story 7.18: Performance/Load Agent Skill Integration**
As a Performance Agent user, I want load test generation and bottleneck analysis delivered via skills.
- AC1: 3 skills deployed: Load Test Generator, Bottleneck Identifier, SLA Validator
- AC2: All classified as low-risk (auto-approved)
- AC3: Token reduction validated: >40%

**Story 7.19: Log Reader Skill Integration**
As a Log Reader user, I want error pattern detection and log summarization delivered via skills.
- AC1: 3 skills deployed: Error Pattern Detector, Log Summarizer, Negative Test Generator
- AC2: All classified as low-risk (auto-approved)
- AC3: Token reduction validated: >50%

**Story 7.20: Documentation & Architecture Update**
As a technical writer, I want all QUALISYS documentation updated to reflect Agent Skills integration, so that the team and stakeholders have accurate reference materials.
- AC1: Architecture document updated: new components, request flows, fallback architecture
- AC2: Agent specifications updated: skill mapping per agent, risk classifications
- AC3: API documentation: Skill Registry API, Skill Proxy API (OpenAPI 3.1)
- AC4: Operational runbooks: skill deployment, rollback, troubleshooting
- AC5: PRD updated: FR-SK requirements cross-referenced
- AC6: Sprint status updated: Epic 7 tracking
- **FRs Covered:** N/A (documentation story)

---

### Story Summary

| Phase | Stories | Duration | Deliverables |
|---|---|---|---|
| Phase 1: POC | 7.1–7.5 | Weeks 1–4 | Registry MVP, 1 skill, Proxy MVP, Adapter MVP, validation report |
| Phase 2: Infrastructure | 7.6–7.10 | Weeks 5–8 | Production registry, scaled proxy, governance, RAG, CI/CD |
| Phase 3: MVP Agents | 7.11–7.15 | Weeks 9–12 | 9 skills, 3 agents integrated, monitoring, regression tests |
| Phase 4: Post-MVP Agents | 7.16–7.20 | Weeks 13–16 | 12 more skills, 4 agents integrated, documentation |
| **Total** | **20 stories** | **16 weeks** | **21 skills, 7 agents, full infrastructure** |

### Story Size Estimates

| Story | Title | Size | Story Points | Notes |
|---|---|---|---|---|
| 7.1 | Skill Registry Service (MVP) | M | 5 | FastAPI service + DB + API |
| 7.2 | BAConsultant Document Parser Skill | S | 3 | Single skill creation |
| 7.3 | Skill Proxy Service (MVP) | L | 8 | Claude API integration + execution engine |
| 7.4 | Skill Adapter Library (MVP) | M | 5 | LangChain bridge + feature flags |
| 7.5 | POC Validation & Metrics | S | 3 | Measurement + report |
| 7.6 | Skill Registry Service (Full) | M | 5 | Versioning + deprecation + caching |
| 7.7 | Skill Proxy Service (Production) | L | 8 | HPA + tenant limits + security hardening |
| 7.8 | Governance Extensions | M | 5 | Risk classification + approval workflows |
| 7.9 | RAG Skill-Aware Pre-Fetching | S | 3 | Filter extension + optimization |
| 7.10 | Skill CI/CD Pipeline | M | 5 | GitHub Actions + Trivy + rollback |
| 7.11 | BAConsultant Full Integration | L | 8 | 3 skills + chaining + validation |
| 7.12 | QAConsultant Skill Integration | M | 5 | 3 skills + validation |
| 7.13 | AutomationConsultant Skill Integration | L | 8 | 3 skills + self-healing integration |
| 7.14 | Observability & Monitoring Dashboard | M | 5 | Prometheus + Grafana + LangFuse + alerts |
| 7.15 | Regression Test Suite | M | 5 | 50+ test cases + CI/CD quality gate |
| 7.16 | DatabaseConsultant Skill Integration | M | 5 | 3 skills (1 high-risk) + governance |
| 7.17 | Security Scanner Skill Integration | M | 5 | 3 skills + approval integration |
| 7.18 | Performance/Load Agent Integration | S | 3 | 3 skills (low-risk, straightforward) |
| 7.19 | Log Reader Skill Integration | S | 3 | 3 skills (low-risk, straightforward) |
| 7.20 | Documentation & Architecture Update | M | 5 | 6 document updates + API docs |
| **Total** | | | **102 SP** | ~25.5 SP per phase (4-week sprints) |

---

## 19. Phased Implementation Roadmap

```
Epic 0  Epic 1  Epic 2  Epic 3  Epic 4  Epic 5  │  Epic 6       │  Epic 7
(Done)  ──────────── MVP (15-19 weeks) ──────────│  Post-MVP     │  Skills Integration
                                                   │  (6-8 weeks)  │  (16 weeks)
                                                   │               │
                                                   │  Advanced     │  Phase 1: POC (4w)
                                                   │  Agents       │  Phase 2: Infra (4w)
                                                   │  SSO/SOC2     │  Phase 3: MVP Skills (4w)
                                                   │  SDK/Market   │  Phase 4: PostMVP Skills (4w)
                                                   │  Self-host    │
                                                   │               │
                                                   │  ← Skills POC │
                                                   │    runs here  │
                                                   │    in parallel│
```

### Key Milestones

| Milestone | Week | Gate |
|---|---|---|
| POC start (parallel with Epic 6) | Epic 6 Week 1 | Architecture Board approval |
| POC validation complete | Epic 6 Week 4 | Go/no-go decision |
| Core infrastructure production-ready | Epic 7 Week 8 | Infrastructure review |
| MVP agents skill-enabled | Epic 7 Week 12 | Regression validation |
| All agents skill-enabled | Epic 7 Week 16 | Full deployment review |
| Cost savings validated | Epic 7 Week 16 + 30 days | Financial review |

---

## 20. Cost-Benefit Analysis

### 20.1 Investment

| Category | Cost | Notes |
|---|---|---|
| Phase 1 (POC) | $40,000 | 4 weeks × 2 engineers |
| Phase 2 (Infrastructure) | $60,000 | 4 weeks × 3 engineers |
| Phase 3 (MVP Integration) | $40,000 | 4 weeks × 2 engineers |
| Phase 4 (Post-MVP Integration) | $40,000 | 4 weeks × 2 engineers |
| **Total Development** | **$180,000** | |
| Infrastructure (Year 1) | $20,400 | Registry ($6K) + Proxy ($12K) + Monitoring ($2.4K) |
| Operational Overhead (Year 1) | $30,000 | +15% engineering maintenance |
| **Total Year 1** | **$230,400** | |

### 20.2 Returns

| Metric | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Tenants | 50 | 100 | 150 |
| Token cost savings | $45,600 | $91,200 | $136,800 |
| Margin improvement | +15% | +20% | +25% |
| Cumulative ROI | -$184,800 | +$60,800 | +$106,400 |

### 20.3 Break-Even

- **Payback period:** 18–24 months
- **3-year ROI:** 1.5x
- **5-year ROI:** 3–4x
- **Strategic value:** Platform extensibility, competitive positioning, marketplace enablement

---

## 21. Risk Assessment & Mitigation

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Skills fail to achieve >40% token reduction | Low | High | POC validates before investment; full-context fallback available |
| R2 | Claude API reliability degrades | Low | High | Auto-fallback to full-context; multi-retry with backoff |
| R3 | Skills add >2s latency | Medium | Medium | Skill metadata caching; container pre-warming; parallel execution |
| R4 | MVP delivery delayed by Skills work | Low | Critical | Skills in separate Epic 7; zero MVP modifications; POC runs parallel |
| R5 | Vendor lock-in (Anthropic) | High | Medium | SkillProvider abstraction interface (see Section 23) |
| R6 | Skill quality inconsistency | Medium | Medium | Automated quality regression suite; deployment approval gates |
| R7 | Governance complexity increases | Medium | Low | Skills use existing approval patterns; minimal new gates |
| R8 | Operational burden >15% | Medium | Medium | Automated deployment/rollback; comprehensive monitoring; clear ownership |
| R9 | Cross-tenant skill data leakage | Low | Critical | Tenant context propagation; RLS on skill tables; stateless execution |
| R10 | Cost overruns on implementation | Medium | Medium | Phased delivery; POC go/no-go gate; incremental investment |

---

## 22. Dependencies & Constraints

### 22.1 Dependencies

| Dependency | Type | Impact if Delayed |
|---|---|---|
| Epic 5 complete (MVP) | Hard | Cannot start Phase 3 (MVP agent integration) |
| Epic 6 complete (Advanced Agents) | Hard | Cannot start Phase 4 (Post-MVP agent integration) |
| Claude API Skills beta availability | Hard | Cannot execute skills without API support |
| Anthropic Skills documentation | Soft | Can work with beta docs; final docs improve quality |
| Agent SDK (Epic 6, Story 6.5) | Soft | Marketplace skills deferred to Epic 8 |

### 22.2 Constraints

| Constraint | Impact | Mitigation |
|---|---|---|
| Claude API rate limits (50 req/s default) | Limits concurrent skill execution | Request quota increase; queuing with backoff |
| 8 skills max per Claude API request | Limits skill parallelism per agent | Most agents need 2–3 skills per invocation |
| Skills require code execution beta headers | API dependency | Monitor beta-to-GA timeline; plan migration |
| Kubernetes resource limits | Limits Skill Proxy scaling | Right-size resource requests; use spot instances |

### 22.3 Claude API Beta Contingency Plan

**Risk:** The Claude API `container` parameter (used for skill execution) is in beta. Anthropic may change the API surface, deprecate the feature, or alter pricing before QUALISYS Epic 7 reaches Phase 3.

**Early Warning Indicators:**
1. Anthropic deprecation notices (monitor [docs.anthropic.com](https://docs.anthropic.com) changelog weekly)
2. Beta header changes (CI integration tests will fail immediately)
3. Rate limit or pricing changes announced
4. Community reports of instability on Anthropic forums/Discord

**Contingency Strategies (ordered by preference):**

**Strategy A: API Migration (1-2 weeks effort)**
- **Trigger:** Anthropic releases GA version of skills with different API surface
- **Action:** Update `AnthropicSkillProvider` to use GA API. SKILL.md files unchanged. `SkillAdapter.translate()` mapping updated.
- **Risk:** Low — this is the expected happy path
- **Impact:** Minimal — isolated to `SkillAdapter` and `SkillProxyService`

**Strategy B: Prompt Engineering Fallback (2-4 weeks effort)**
- **Trigger:** Anthropic deprecates `container` parameter without replacement
- **Action:** Implement `PromptEngineeringSkillProvider` that injects SKILL.md content directly into the system prompt using progressive disclosure via prompt structure:
  - Level 1: Always in system prompt (skill descriptions)
  - Level 2: Injected into system prompt only when skill selected (instructions section)
  - Level 3: Appended to user message on demand (resources)
- **Architecture change:** Skill Proxy Service becomes a prompt construction service instead of a Claude API bridge. No container execution — pure prompt engineering.
- **Token impact:** ~20-30% less efficient than native container execution (skill instructions consume context window), but still 30-40% better than full-context mode
- **Risk:** Medium — reduced token savings, but core value proposition preserved
- **SKILL.md files:** Unchanged — they contain LLM-agnostic instructions

```python
class PromptEngineeringSkillProvider(SkillProvider):
    """Fallback: inject skill content via prompt engineering."""

    def execute_skill(self, skill_id: str, instructions: str,
                      context: dict) -> SkillResult:
        # Load SKILL.md Level 2 instructions
        skill_instructions = self.registry.get_instructions(skill_id)

        # Inject into system prompt (not container)
        enhanced_system = (
            f"{context['system']}\n\n"
            f"--- Active Skill: {skill_id} ---\n"
            f"{skill_instructions}\n"
            f"--- End Skill ---\n\n"
            f"Execute the above skill instructions for the user's request."
        )

        # Standard Claude API call (no container parameter)
        response = self.client.messages.create(
            model=context.get("model", "claude-sonnet-4-5-20250514"),
            max_tokens=context.get("max_tokens", 8192),
            system=enhanced_system,
            messages=context["messages"],
        )
        return self._to_skill_result(response)
```

**Strategy C: Multi-Provider Skill Execution (4-6 weeks effort)**
- **Trigger:** Anthropic exits API business or pricing becomes untenable
- **Action:** Implement `GenericSkillProvider` using OpenAI or self-hosted vLLM with prompt engineering approach from Strategy B
- **Architecture change:** Skill Proxy routes to alternative LLM. `SkillProvider` abstraction (Section 23) makes this a backend swap.
- **Risk:** Medium-High — different LLMs may produce different quality outputs. Regression testing required per-skill.
- **SKILL.md files:** Unchanged — LLM-agnostic by design

**Decision Gate:** POC Phase (Story 7.5) validates Claude API stability. If beta instability observed during POC, escalate to Architecture Board before Phase 2 investment. The go/no-go decision (Story 7.5 AC7) explicitly includes API stability assessment.

**Monitoring (implemented in Story 7.3):**
- Claude API response time tracking (alert if P95 >5s, indicating instability)
- Beta header acceptance monitoring (alert if 4xx responses spike)
- Anthropic changelog RSS feed monitoring (automated Slack alerts)

---

## 23. Vendor Lock-in Mitigation Strategy

### 23.1 Abstraction Layer

```python
from abc import ABC, abstractmethod

class SkillProvider(ABC):
    """Abstract interface for skill execution providers."""

    @abstractmethod
    def execute_skill(self, skill_id: str, instructions: str,
                      context: dict) -> SkillResult:
        """Execute a skill with given instructions and context."""
        pass

    @abstractmethod
    def list_skills(self) -> list[SkillMetadata]:
        """List available skills."""
        pass

class AnthropicSkillProvider(SkillProvider):
    """Anthropic Claude API skill execution."""
    def execute_skill(self, skill_id, instructions, context):
        # Uses Claude API with container parameter
        ...

class GenericSkillProvider(SkillProvider):
    """Generic LLM skill execution (future: OpenAI, self-hosted)."""
    def execute_skill(self, skill_id, instructions, context):
        # Translates skill instructions to generic LLM prompt
        # Progressive disclosure via prompt engineering
        ...
```

### 23.2 Migration Path

| Scenario | Strategy | Effort |
|---|---|---|
| Claude API becomes expensive | Swap `AnthropicSkillProvider` → `GenericSkillProvider` | 2–4 weeks |
| Skills API deprecated | Implement progressive disclosure via prompt engineering | 4–6 weeks |
| Alternative skill framework emerges | Implement new `SkillProvider` | 2–4 weeks per provider |

### 23.3 Key Principle

Skills are implemented as **instructions in SKILL.md files** — not as Claude-specific API constructs. The SKILL.md files contain domain knowledge that is LLM-agnostic. Only the execution mechanism (Claude API container parameter) is Claude-specific, and that's isolated behind the `SkillProvider` abstraction.

---

## 24. Documentation Update Plan

| Document | Updates Required | Owner | Phase |
|---|---|---|---|
| `docs/architecture/architecture.md` | New components diagram, skill request flow, fallback architecture, database schema | Architect | Phase 2 |
| `docs/planning/agent-specifications.md` | Skill mapping per agent, risk classifications, governance extensions | PM | Phase 3 |
| `docs/planning/prd.md` | Cross-reference FR-SK requirements, Epic 7 addition | PM | Phase 4 |
| `docs/epics/epics.md` | Add Epic 7 with 20 stories | PM | Phase 1 |
| `docs/sprint-status.yaml` | Add Epic 7 tracking | SM | Phase 1 |
| API Documentation (OpenAPI 3.1) | Skill Registry API, Skill Proxy API | Dev | Phase 2 |
| Operational Runbooks | Skill deployment, rollback, troubleshooting, monitoring | DevOps | Phase 2 |
| Grafana Dashboard Configs | 5 skill dashboards | DevOps | Phase 3 |

---

## 25. Appendix: Decision Log

| # | Decision | Rationale | Date | Status |
|---|---|---|---|---|
| D1 | Adopt Post-MVP (Epic 7, not during MVP) | Skills are optimization, not core. MVP delivery is #1 priority. | 2026-02-14 | Approved (per evaluation docs) |
| D2 | Defer MCP → Skill Bridge to Epic 8 | Bridge adds latency (+200–500ms) and complexity (1 new service) for limited value. Skills and MCP can operate independently. | 2026-02-14 | Proposed |
| D3 | POC runs parallel with Epic 6 | Validates benefits before Epic 7 investment. No impact on Epic 6 timeline (separate team). | 2026-02-14 | Proposed |
| D4 | Hybrid approach: skills + custom agent logic | Skills for complex workflows, custom logic for simple tasks. Not all-or-nothing. | 2026-02-14 | Proposed |
| D5 | SkillProvider abstraction for vendor lock-in | SKILL.md files are LLM-agnostic knowledge. Only execution mechanism is Claude-specific, isolated behind interface. | 2026-02-14 | Proposed |
| D6 | Zero regression guarantee via full-context fallback | Every skill-enabled agent path has fallback. Skills never become hard dependency. | 2026-02-14 | Proposed |
| D7 | Skills tables in tenant schemas (not global) | Consistent with existing multi-tenant pattern. RLS enforcement. Tenant-scoped audit trails. | 2026-02-14 | Proposed |
| D8 | 21 skills across 7 agents | Comprehensive coverage. 9 MVP agent skills (Phase 3) + 12 Post-MVP agent skills (Phase 4). | 2026-02-14 | Proposed |
| D9 | Feature flags per agent for gradual rollout | Each agent can be independently skill-enabled/disabled. Reduces blast radius. | 2026-02-14 | Proposed |
| D10 | Skill A/B testing deferred to optimization phase | Core infrastructure first. A/B testing adds complexity best addressed after initial rollout. | 2026-02-14 | Proposed |

---

**Document Status:** Draft — Pending Architecture Board Approval
**Next Review:** Architecture Board Review
**Approval Required:** Architecture Board, Product Council, Engineering Lead
**Author:** John (PM Agent)
**Requested By:** Azfar
