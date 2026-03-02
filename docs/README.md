# QUALISYS Documentation Index

This directory contains all planning, architecture, implementation, and research documentation for the QUALISYS AI System Quality Assurance Platform.

## Quick Navigation

| I want to... | Go to |
|-------------|-------|
| Understand the product vision | [Product Brief](./planning/product-brief-QUALISYS-2025-12-01.md) |
| Read all functional requirements | [PRD](./planning/prd.md) |
| See the system architecture | [Architecture](./architecture/architecture.md) |
| Find the current sprint status | [Sprint Status](./sprint-status.yaml) |
| See what's in each epic | [Epic Overview](./epics/epics.md) |
| Find a specific story | [Stories by Epic](./stories/) |
| Set up the local environment | [Local Development Guide](./local-development.md) |

---

## Directory Structure

```
docs/
├── planning/           # Strategic and product planning documents
├── architecture/       # System architecture and technical design
├── epics/              # Epic definitions (8 epics, 132 stories)
├── tech-specs/         # Per-epic technical specifications and validation reports
├── stories/            # Story files organised by epic
│   ├── epic-0/         # Infrastructure Foundation (22 stories — done)
│   ├── epic-1/         # Foundation & Administration (13 stories — done)
│   └── epic-2/         # AI Agent Platform (13/18 done, 5 backlog)
├── designs/            # UI designs and mockups
│   └── mockups/        # 8 workflow screen mockups (PNG)
├── evaluations/        # Architecture board evaluations and technical reviews
├── reports/            # Validation and readiness reports
├── research/           # Market and competitive research
├── sprint-changes/     # Approved sprint scope change proposals
└── secrets/            # Third-party credential inventory and rotation guide
```

---

## Planning Documents

| Document | Description |
|----------|-------------|
| [PRD](./planning/prd.md) | 147 functional requirements across 16 categories |
| [Agent Skills Integration PRD](./planning/prd-agent-skills-integration.md) | 28 FRs for progressive skill loading and cost optimisation |
| [Agent Extensibility Tech Spec](./planning/tech-spec-agent-extensibility-framework.md) | Custom agent platform architecture |
| [Agent Specifications](./planning/agent-specifications.md) | 7 agent definitions, RBAC, governance, skill mapping |
| [Product Brief](./planning/product-brief-QUALISYS-2025-12-01.md) | Market positioning and strategic vision |
| [UX Design Specification](./planning/ux-design-specification.md) | 6 personas, 6 critical user flows, design system |
| [Test Design System](./planning/test-design-system.md) | Test strategy, patterns, and quality framework |

---

## Architecture & Implementation

| Document | Description |
|----------|-------------|
| [System Architecture](./architecture/architecture.md) | Technical design, ADRs, risk analysis (3,900+ lines) |
| [Epic Overview](./epics/epics.md) | 8 epics, 132 stories, complete breakdown |
| [Sprint Status](./sprint-status.yaml) | Real-time implementation tracking (story lifecycle) |
| [BMM Workflow Status](./bmm-workflow-status.yaml) | BMad Method phase tracking |
| [Local Development Guide](./local-development.md) | Complete environment setup guide |

---

## Technical Specifications

| Document | Epic | Status |
|----------|------|--------|
| [Epic 0 Tech Spec](./tech-specs/tech-spec-epic-0.md) | Infrastructure Foundation | Complete |
| [Epic 1 Tech Spec](./tech-specs/tech-spec-epic-1.md) | Foundation & Administration | Complete (validated) |
| [Epic 1 Tech Spec Validation](./tech-specs/validation-report-tech-spec-epic-1-20260221.md) | Epic 1 | Fully remediated |
| [Epic 2 Tech Spec](./stories/epic-2/tech-spec-epic-2.md) | AI Agent Platform | Active |

---

## Stories

Stories are organised by epic under `docs/stories/`. Each story has two files:
- `{story-id}.md` — Story definition, acceptance criteria, tasks, and dev agent record
- `{story-id}.context.xml` — Assembled context (docs + code snippets) for the DEV agent

| Epic | Directory | Status |
|------|-----------|--------|
| Epic 0 — Infrastructure Foundation | [stories/epic-0/](./stories/epic-0/) | 22/22 done ✅ |
| Epic 1 — Foundation & Administration | [stories/epic-1/](./stories/epic-1/) | 13/13 done ✅ |
| Epic 2 — AI Agent Platform | [stories/epic-2/](./stories/epic-2/) | 13/18 done 🔄 |

---

## Validation & Reports

| Document | Description |
|----------|-------------|
| [Implementation Readiness Report](./reports/implementation-readiness-report-2026-01-22.md) | Phase 3 → Phase 4 validation (8.7/10) |
| [PRD Validation](./reports/validation-report-prd-20251211.md) | PRD completeness and quality validation |
| [Architecture Validation](./reports/validation-report-architecture-20260214.md) | Architecture document validation |
| [Architecture Board Review — Agent Skills](./reports/architecture-board-review-agent-skills-20260215.md) | Agent Skills integration approval (7.8/10) |

---

## Research & Evaluations

| Document | Description |
|----------|-------------|
| [Market Research](./research/research-market-2025-11-30.md) | Market size, CAGR, growth projections |
| [Competitive Research](./research/research-competitive-2025-12-01.md) | DeepEval, Braintrust, Humanloop analysis |
| [Agent Skills — Technical Review](./evaluations/anthropic-agent-skills-technical-review.md) | Integration feasibility and risk analysis |
| [Agent Skills — Executive Strategy](./evaluations/anthropic-agent-skills-executive-strategy.md) | Business case, competitive positioning, ROI |
| [Agent Skills — Architecture Board](./evaluations/anthropic-agent-skills-architecture-board.md) | Architecture board evaluation |

---

## Sprint Change Proposals

| Date | Proposal | Impact |
|------|----------|--------|
| 2026-01-24 | [Docker → Podman Migration](./sprint-changes/sprint-change-proposal-2026-01-24.md) | 9 documents updated |
| 2026-02-06 | [Agent Restructuring (8 → 7 agents)](./sprint-changes/sprint-change-proposal-2026-02-06.md) | Consolidated agent count |
| 2026-02-09 | [Multi-cloud AWS + Azure](./sprint-changes/sprint-change-proposal-2026-02-09.md) | Two Roots architecture |
| 2026-02-20 | [Backend Tech Stack Correction](./sprint-changes/sprint-change-proposal-2026-02-20.md) | TypeScript → Python/FastAPI |

---

## UI Designs

| Screen | Mockup |
|--------|--------|
| Project Setup | [mockups/1 - Project Setup.png](./designs/mockups/1%20-%20Project%20Setup.png) |
| Upload & Connect | [mockups/2 - Upload & Connect.png](./designs/mockups/2%20-%20Upload%20%26%20Connect.png) |
| Agent Selection | [mockups/3 - Agent Selection.png](./designs/mockups/3%20-%20Agent%20Selection.png) |
| Agent Execution | [mockups/4 - Agent Execution.png](./designs/mockups/4%20-%20Agent%20Execution.png) |
| Coverage Matrix | [mockups/5 - Coverage Matrix.png](./designs/mockups/5%20-%20Coverage%20Matrix.png) |
| Manual Testing | [mockups/6 - Manual Testing.png](./designs/mockups/6%20-%20Manual%20Testing.png) |
| Self-Healing | [mockups/7 - Self-Healing.png](./designs/mockups/7%20-%20Self-Healing.png) |
| Executive Dashboard | [mockups/8 - Executive Dashboard.png](./designs/mockups/8%20-%20Executive%20Dashboard.png) |

Full interactive design file: [`docs/designs/qualisys-ui-workflow.pen`](./designs/qualisys-ui-workflow.pen)

---

## Naming Conventions

- **Stories:** `{epic-id}-{seq}-{slug}.md` e.g. `2-11-artifact-editing-versioning.md`
- **Context XMLs:** Same name as story with `.context.xml` extension
- **Tech Specs:** `tech-spec-epic-{n}.md`
- **Validation Reports:** `validation-report-{subject}-{YYYYMMDD}.md`
- **Sprint Changes:** `sprint-change-proposal-{YYYY-MM-DD}.md`
