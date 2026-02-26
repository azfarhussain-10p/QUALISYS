# QUALISYS Project Documentation Index

**AI-Powered Testing Platform**

---

## Project Status

| Metric | Value |
|--------|-------|
| **Current Phase** | Phase 4: Implementation |
| **Current Epic** | Epic 2 - AI Agent Platform & Executive Visibility |
| **Track** | Enterprise BMad Method |
| **Stories** | 108 total (100 MVP + 8 Post-MVP) |
| **Completed** | Epic 0 (22/22 stories), Epic 1 (13/13 stories) |

---

## Directory Structure

```
docs/
├── index.md                    # This file - documentation index
├── bmm-workflow-status.yaml    # Overall BMad workflow tracking
├── sprint-status.yaml          # Sprint & story status tracking
│
├── planning/                   # Phase 2: Planning Artifacts
│   ├── prd.md                  # Product Requirements Document
│   ├── product-brief-*.md      # Product brief
│   ├── ux-design-specification.md
│   └── test-design-system.md
│
├── architecture/               # Phase 3: Architecture & Solutioning
│   └── architecture.md         # System architecture document
│
├── research/                   # Phase 1: Research & Analysis
│   ├── research-market-*.md    # Market research
│   └── research-competitive-*.md
│
├── epics/                      # Epic Definitions
│   ├── epics.md                # All epics overview (78 MVP stories)
│   └── epic-0-infrastructure.md # Epic 0 detailed breakdown
│
├── stories/                    # Story Files — organised by epic subdir
│   ├── epic-0/                 # Epic 0 stories (22 .md + 22 .context.xml)
│   ├── epic-1/                 # Epic 1 stories (13 .md + 13 .context.xml + retro)
│   └── epic-2/                 # Epic 2 stories (placeholder, ready for drafting)
│
├── tech-specs/                 # Epic Technical Specifications
│   ├── tech-spec-epic-0.md     # Infrastructure tech spec
│   └── tech-spec-epic-1.md     # Foundation & Admin tech spec
│
├── reports/                    # Validation & Readiness Reports
│   ├── validation-report-prd-*.md
│   ├── validation-report-architecture-*.md
│   └── implementation-readiness-report-*.md
│
├── sprint-changes/             # Sprint change proposals (course corrections)
│   └── sprint-change-proposal-*.md
└── _archive/                   # Original Source Files
    ├── QUALISYS AI Powered Testing Platform.docx
    └── QUALISYS-Project-Documentation.md
```

---

## Quick Links by Phase

### Phase 1: Research & Analysis
- [Market Research](./research/research-market-2025-11-30.md)
- [Competitive Research](./research/research-competitive-2025-12-01.md)

### Phase 2: Planning
- [Product Brief](./planning/product-brief-QUALISYS-2025-12-01.md)
- [PRD - Product Requirements Document](./planning/prd.md)
- [UX Design Specification](./planning/ux-design-specification.md)
- [Test Design System](./planning/test-design-system.md)

### Phase 3: Solutioning
- [System Architecture](./architecture/architecture.md)
- [PRD Validation Report](./reports/validation-report-prd-20251211.md)
- [Architecture Validation Report](./reports/validation-report-architecture-20251211.md)
- [Implementation Readiness Report](./reports/implementation-readiness-report-2026-01-22.md)

### Phase 4: Implementation
- [Sprint Status](./sprint-status.yaml) - Current sprint tracking
- [All Epics Overview](./epics/epics.md) - Epic breakdown with stories
- [Epic 0 Details](./epics/epic-0-infrastructure.md) - Infrastructure foundation ✅
- [Epic 0 Tech Spec](./tech-specs/tech-spec-epic-0.md)
- [Epic 1 Tech Spec](./tech-specs/tech-spec-epic-1.md)
- [Epic 1 Retrospective](./stories/epic-1/epic-1-retro-2026-02-26.md) - Post-epic lessons learned ✅
- [Sprint Change Proposals](./sprint-changes/) - Course correction history

---

## Epic Overview

| Epic | Name | Stories | Status | Priority |
|------|------|---------|--------|----------|
| 0 | Infrastructure Foundation | 22 | **completed** | P0 CRITICAL |
| 1 | Foundation & Administration | 13 | **completed** | P1 HIGH |
| 2 | AI Agent Platform & Executive Visibility | 18 | **next** | P1 HIGH |
| 3 | Manual Testing & Developer Integration | 15 | backlog | P1 HIGH |
| 4 | Automated Execution & Self-Healing | 16 | backlog | P0 CRITICAL |
| 5 | Complete Dashboards & Ecosystem Integration | 16 | backlog | P1 HIGH |
| 6 | Advanced Features (Post-MVP) | 8 | backlog | P2 |

---

## Key Technical Decisions

### Cloud Platform
- **Selected**: AWS + Azure (Two Roots architecture, build-time choice per deployment)
- **Rationale**: Team expertise, multi-cloud flexibility, managed services quality

### Architecture
- **Multi-Tenant**: Schema-per-tenant PostgreSQL with RLS
- **Container Orchestration**: Kubernetes (EKS or AKS)
- **Caching**: Redis 7+ cluster mode
- **CI/CD**: GitHub Actions

### AI/ML Stack
- **Agent Framework**: LangChain
- **Primary LLM**: OpenAI GPT-4 (MVP), self-hosted option (Epic 6+)
- **Vector DB**: pgvector

### Frontend/Backend
- **Frontend**: React 18 + Vite + TypeScript + Tailwind CSS
- **Backend**: Python FastAPI (Python 3.11+)
- **Testing**: Playwright (browser automation)

---

## BMad Workflow Commands

```bash
# Check current status
/bmad:bmm:workflows:workflow-status

# Sprint planning (SM agent)
/bmad:bmm:workflows:sprint-planning

# Create next story (SM agent)
/bmad:bmm:workflows:create-story

# Mark story ready for dev (SM agent)
/bmad:bmm:workflows:story-ready

# Implement story (DEV agent)
/bmad:bmm:workflows:dev-story
```

---

## Project Overview

QUALISYS is an AI-powered testing platform combining:
- Document ingestion & understanding
- DOM analysis & source code comprehension
- Multi-agent AI test generation
- Self-healing test automation
- Comprehensive dashboards & integrations

### Target Personas
- PM / CSM (Project Managers / Customer Success Managers)
- Manual QA Engineers
- QA Automation Engineers
- Developers
- Owners/Admins

### Core Value Proposition
1. **Ingest** docs + app DOM + source code
2. **Produce** comprehensive test artifacts via AI agents
3. **Run tests** (manual + automated)
4. **Self-heal** broken tests automatically
5. **Provide** dashboards, KPIs, SLAs, defect flows

---

**Last Updated**: 2026-02-26
**Maintained By**: QUALISYS Development Team
