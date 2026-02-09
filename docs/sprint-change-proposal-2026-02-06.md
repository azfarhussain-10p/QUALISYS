# Sprint Change Proposal — Agent Restructuring

**Date:** 2026-02-06
**Author:** PM Agent (John)
**Change Scope:** MAJOR
**Status:** Pending Approval

---

## 1. Issue Summary

### Problem Statement
The current QUALISYS planning documentation (PRD, Architecture, Epics, Stories, UX Design, Sprint Status) references an 8-agent architecture with narrow specialist agents. Based on new research and strategic refinement (documented in `docs/improvements/`), the platform's agent structure is being consolidated from 8 specialized agents into 6 comprehensive consultant agents with clearer responsibility boundaries.

### Context
- **Discovery Date:** 2026-02-03 (research document) and 2026-02-06 (AutomationConsultant research)
- **Trigger:** Strategic product evolution — not a failure, but an improvement based on deeper analysis of agent responsibilities, governance needs, and operational efficiency
- **Current State:** Epic 0 (Infrastructure) is active with 10/22 stories complete. No application code references agents yet. All agent references exist only in planning documents.

### Agent Consolidation Map

| Old Agent(s) | New Agent | Scope |
|-------------|-----------|-------|
| Documentation Analyzer | **BAConsultant AI Agent** | Requirements extraction, user story creation, quality scoring, gap/ambiguity detection, traceability |
| Manual Tester + Test Case Generator | **QAConsultant AI Agent** | Test strategy, manual test cases, BDD scenarios, checklists, test data generation, sprint readiness (dual role: Test Consultant + ScrumMaster) |
| Automation Tester + Web Scraper | **AutomationConsultant AI Agent** | Framework architecture, script generation (Playwright/Puppeteer/REST-Assured), self-healing, DOM crawling/discovery, CI/CD integration, automation suites |
| AI Log Reader/Summarizer | AI Log Reader/Summarizer | *Unchanged (Post-MVP)* |
| Security Scanner Orchestrator | Security Scanner Orchestrator | *Unchanged (Post-MVP)* |
| Performance/Load Agent | Performance/Load Agent | *Unchanged (Post-MVP)* |

### MVP vs Post-MVP Boundary

**MVP (3 Agents):**
1. BAConsultant AI Agent
2. QAConsultant AI Agent
3. AutomationConsultant AI Agent

**Post-MVP (3 Agents):**
4. AI Log Reader / Summarizer
5. Security Scanner Orchestrator
6. Performance / Load Agent

**Total: 6 agents (was 8)**

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | Impact Level | Details |
|------|-------------|---------|
| Epic 0: Infrastructure Foundation | NONE | No agent references. Currently active. No changes needed. |
| Epic 1: Foundation & Administration | NONE | Auth, RBAC, Projects — no agent references. No changes needed. |
| Epic 2: AI Agent Platform & Executive Visibility | **HIGH** | 31+ old agent name references. FR32-37 need agent name updates. "4 MVP agents" → "3 MVP agents". Agent selection UI, pipeline orchestration stories need updating. |
| Epic 3: Manual Testing & Developer Integration | **MEDIUM** | "Manual Tester agent" → "QAConsultant AI Agent" in FR33-34 references. Core functionality unchanged. |
| Epic 4: Automated Execution & Self-Healing | **MEDIUM** | "Automation Tester agent" → "AutomationConsultant AI Agent". Self-healing capabilities strengthened by consolidation. |
| Epic 5: Complete Dashboards & Ecosystem Integration | **LOW** | Minimal direct agent references. Agent-related dashboard labels may need updating. |
| Epic 6: Post-MVP Advanced Features | **HIGH** | Remove Story 6-1 (web-scraper-agent — absorbed into AutomationConsultant). Rename Stories 6-2 through 6-4. Add new story for BAConsultant expanded capabilities. |

### 2.2 Artifact Impact

| Document | Old Agent Refs | "8 Agents" Refs | Total Changes | Severity |
|----------|---------------|-----------------|---------------|----------|
| `docs/planning/prd.md` | 13 | 3 | 16 | HIGH |
| `docs/epics/epics.md` | 31 | 1 | 32 | HIGH |
| `docs/architecture/architecture.md` | 3 | 7 | 10 | HIGH |
| `docs/planning/ux-design-specification.md` | 10 | 1 | 11 | MEDIUM |
| `README.md` | 7 | 1 | 8 | MEDIUM |
| `docs/sprint-status.yaml` | 4 | 0 | 4 | MEDIUM |
| `docs/reports/implementation-readiness-report-2026-01-22.md` | 0 | 2 | 2 | LOW |
| `docs/reports/validation-report-architecture-20251211.md` | 0 | 1 | 1 | LOW |
| `docs/research/research-market-2025-11-30.md` | 0 | 1 | 1 | LOW |
| **TOTAL** | **68** | **17** | **~85** | |

### 2.3 Technical Impact

- **No code changes required** — no application code exists yet (only infrastructure IaC)
- **No infrastructure changes** — agent restructuring doesn't affect Terraform, Kubernetes, or CI/CD
- **No database schema changes** — agent orchestration tables haven't been implemented yet
- **No deployment changes** — all changes are documentation/planning artifacts only

### 2.4 What's NOT Changing

- Epic 0 and Epic 1 remain completely unchanged
- All infrastructure work (10 completed stories) is unaffected
- Tech specs for Epic 0 and Epic 1 are unaffected
- Multi-tenancy architecture unchanged
- Self-healing architecture unchanged (strengthened by AutomationConsultant consolidation)
- Integration architecture unchanged (JIRA, TestRail, GitHub, Slack)
- RBAC and persona definitions unchanged (6 personas remain)
- Non-functional requirements unchanged

---

## 3. Recommended Approach

### Selected Path: Option 1 — Direct Adjustment

**Rationale:**
1. **Zero code impact** — all changes are document-level substitutions
2. **No functionality removed** — capabilities are consolidated, not cut
3. **Consolidation strengthens the design** — 3 comprehensive consultant agents > 4 narrow specialists
4. **Perfect timing** — before any feature code references agents
5. **Clear specifications available** — research docs define all 3 MVP agents thoroughly
6. **No timeline impact** — document updates are a fraction of sprint work

**Effort Estimate:** Medium (document updates across ~9 files, ~85 individual changes)
**Risk Level:** Low (name substitutions + count updates, no structural changes)
**Timeline Impact:** None — can be completed in parallel with ongoing Epic 0 work

### What Changes

**Category 1: Agent Name Substitutions (mechanical)**
- "Documentation Analyzer" → "BAConsultant AI Agent" (everywhere)
- "Manual Tester" → "QAConsultant AI Agent" (everywhere)
- "Test Case Generator" → "QAConsultant AI Agent" (everywhere)
- "Automation Tester" → "AutomationConsultant AI Agent" (everywhere)
- "Web Scraper" → absorbed into AutomationConsultant (remove as standalone)

**Category 2: Count Updates**
- "8 specialized AI agents" → "6 specialized AI agents (3 MVP + 3 Post-MVP)"
- "4 MVP agents" → "3 MVP agents"
- "4 Post-MVP agents" → "3 Post-MVP agents"

**Category 3: Structural Updates**
- PRD Executive Summary: Rewrite agent list to reflect new 3+3 structure
- PRD MVP Scope: Update "Multi-Agent Test Generation" section
- PRD Growth Features: Update Post-MVP agent list (remove Web Scraper, keep 3)
- Epics: Epic 2 agent references, Epic 6 story restructuring
- Architecture: Agent orchestration references, SWOT analysis agent counts
- UX Design: Agent Cards, agent selection flow descriptions
- Sprint Status: Epic 6 stories (remove 6-1, rename 6-2 through 6-4, update counts)

**Category 4: Enhanced FR Definitions**
Based on research documents, the following FRs should be enhanced to reflect expanded agent capabilities:

- **FR32** (OLD): "Documentation Analyzer agent generates requirements-to-test coverage matrix"
  **FR32** (NEW): "BAConsultant AI Agent analyzes uploaded requirements, performs gap/ambiguity detection, generates requirements-to-test coverage matrix, and creates user stories with acceptance criteria and quality scoring"

- **FR33** (OLD): "Manual Tester agent generates manual test checklists with step-by-step instructions"
  **FR33** (NEW): "QAConsultant AI Agent generates manual test checklists with step-by-step instructions, supporting checklist-driven testing across Smoke, Sanity, Integration, Regression, Usability, and UAT testing types"

- **FR34** (OLD): "Manual Tester agent generates exploratory testing prompts and scenarios"
  **FR34** (NEW): "QAConsultant AI Agent generates exploratory testing prompts, BDD/Gherkin scenarios, negative test cases, boundary condition tests, and domain-aware synthetic test data"

- **FR35** (OLD): "Automation Tester agent generates Playwright test scripts with smart locators"
  **FR35** (NEW): "AutomationConsultant AI Agent generates automated test scripts (Playwright, Puppeteer, REST-Assured) with smart locators, supporting multiple framework architectures (POM, Data-Driven, Hybrid)"

- **FR36** (OLD): "Test Case Generator agent creates BDD/Gherkin scenarios from requirements"
  **FR36** (NEW): "QAConsultant AI Agent creates test strategy documents, test plans, and validates sprint readiness"

- **FR37** (OLD): "Test Case Generator agent creates negative test cases and boundary condition tests"
  **FR37** (NEW): "AutomationConsultant AI Agent performs automated DOM crawling, sitemap generation, and coverage gap detection for application discovery"

**Note on FR36/FR37:** The original Test Case Generator's BDD/Gherkin capability is absorbed into FR34 (QAConsultant). FR36-37 are repurposed for genuinely new capabilities from the research docs that weren't covered by existing FRs. This avoids adding new FR numbers while ensuring all new capabilities are captured.

---

## 4. Detailed Change Proposals

### 4.1 PRD Changes (`docs/planning/prd.md`)

**Change P1: Executive Summary — Agent List**
```
Section: Executive Summary, paragraph 3 (line ~15)

OLD:
"uses 8 specialized AI agents to automatically generate comprehensive test artifacts"

NEW:
"uses 6 specialized AI agents (3 MVP + 3 Post-MVP) to automatically generate comprehensive test artifacts"
```
**Rationale:** Reflects new agent count.

**Change P2: Executive Summary — "What Makes This Special" Section**
```
Section: What Makes This Special, item 1 (line ~27)

OLD:
"8 specialized AI agents (Documentation Analyzer, Manual Tester, Automation Tester, Web Scraper, AI Log Reader/Summarizer, Test Case Generator, Security Scanner Orchestrator, Performance/Load Agent)"

NEW:
"6 specialized AI agents — MVP: BAConsultant AI Agent, QAConsultant AI Agent, AutomationConsultant AI Agent; Post-MVP: AI Log Reader/Summarizer, Security Scanner Orchestrator, Performance/Load Agent — work in orchestrated pipelines"
```
**Rationale:** Reflects new agent names and MVP/Post-MVP split.

**Change P3: MVP Scope — Multi-Agent Test Generation**
```
Section: Product Scope > MVP > Core Capabilities > 3. Multi-Agent Test Generation (lines ~164-169)

OLD:
"3. Multi-Agent Test Generation (MVP Agents)"
"- Documentation Analyzer: Requirements → coverage matrix"
"- Manual Tester: Generate manual test checklists + exploratory test prompts"
"- Automation Tester: Generate Playwright/Puppeteer scripts with smart locators"
"- Test Case Generator: BDD/Gherkin scenarios + negative cases + boundary analysis"

NEW:
"3. Multi-Agent Test Generation (MVP Agents)"
"- BAConsultant AI Agent: Requirements analysis, gap/ambiguity detection, coverage matrix, user story creation with quality scoring"
"- QAConsultant AI Agent: Test strategy, manual test checklists, BDD/Gherkin scenarios, negative/boundary tests, checklist-driven testing, synthetic test data, sprint readiness validation"
"- AutomationConsultant AI Agent: Playwright/Puppeteer/REST-Assured script generation, framework architecture (POM/Data-Driven/Hybrid), DOM crawling and discovery, automation suite management, CI/CD integration"
```
**Rationale:** Reflects consolidated agents with expanded capabilities from research docs.

**Change P4: NOT in MVP Section**
```
Section: Product Scope > MVP > NOT in MVP (line ~196)

OLD:
"- ❌ Advanced AI agents (Web Scraper, Log Reader, Security Scanner, Performance Agent)"

NEW:
"- ❌ Post-MVP AI agents (AI Log Reader/Summarizer, Security Scanner Orchestrator, Performance/Load Agent)"
```
**Rationale:** Web Scraper no longer post-MVP (absorbed into AutomationConsultant). Only 3 agents deferred.

**Change P5: Growth Features**
```
Section: Growth Features > Phase 1 (lines ~208-210)

OLD:
"**Phase 1: Complete Multi-Agent Suite**
- Add remaining agents: Web Scraper, AI Log Reader/Summarizer, Security Scanner Orchestrator, Performance/Load Agent"

NEW:
"**Phase 1: Complete Multi-Agent Suite**
- Add remaining agents: AI Log Reader/Summarizer, Security Scanner Orchestrator, Performance/Load Agent"
```
**Rationale:** Web Scraper removed from growth phase (absorbed into MVP AutomationConsultant).

**Change P6: FR32-37 Updates**
```
Section: Functional Requirements > Test Artifact Generation (lines ~470-477)

OLD:
"- FR32: Documentation Analyzer agent generates requirements-to-test coverage matrix"
"- FR33: Manual Tester agent generates manual test checklists with step-by-step instructions"
"- FR34: Manual Tester agent generates exploratory testing prompts and scenarios"
"- FR35: Automation Tester agent generates Playwright test scripts with smart locators"
"- FR36: Test Case Generator agent creates BDD/Gherkin scenarios from requirements"
"- FR37: Test Case Generator agent creates negative test cases and boundary condition tests"

NEW:
"- FR32: BAConsultant AI Agent analyzes requirements, performs gap/ambiguity detection, and generates requirements-to-test coverage matrix with user story quality scoring"
"- FR33: QAConsultant AI Agent generates manual test checklists with step-by-step instructions, supporting checklist-driven testing across Smoke, Sanity, Integration, Regression, Usability, and UAT types"
"- FR34: QAConsultant AI Agent generates exploratory testing prompts, BDD/Gherkin scenarios, negative test cases, boundary condition tests, and domain-aware synthetic test data"
"- FR35: AutomationConsultant AI Agent generates automated test scripts (Playwright, Puppeteer, REST-Assured) with smart locators, supporting multiple framework architectures (POM, Data-Driven, Hybrid)"
"- FR36: QAConsultant AI Agent creates test strategy documents, test plans, and validates sprint readiness"
"- FR37: AutomationConsultant AI Agent performs automated DOM crawling, sitemap generation, and coverage gap detection for application discovery"
```
**Rationale:** Reflects new agent ownership with expanded capabilities from research docs.

### 4.2 Architecture Changes (`docs/architecture/architecture.md`)

**Change A1: All "8 specialized AI agents" → "6 specialized AI agents (3 MVP + 3 Post-MVP)"** (7 occurrences)

**Change A2: All "8 AI agents" → "6 AI agents"** (additional occurrences)

**Change A3: Old agent names → New names** (3 occurrences)
- "Documentation Analyzer" → "BAConsultant AI Agent"
- "Manual Tester" → "QAConsultant AI Agent"
- "Automation Tester" → "AutomationConsultant AI Agent"

### 4.3 Epics Changes (`docs/epics/epics.md`)

**Change E1: Epic 2 — Agent References** (31+ occurrences)
All references to old 4 MVP agents updated to new 3 MVP agents:
- "Documentation Analyzer" → "BAConsultant AI Agent"
- "Manual Tester" → "QAConsultant AI Agent"
- "Test Case Generator" → "QAConsultant AI Agent"
- "Automation Tester" → "AutomationConsultant AI Agent"

**Change E2: Epic 2 — Value Delivered Section**
```
OLD:
"Select 4 MVP AI agents (Documentation Analyzer, Manual Tester, Automation Tester, Test Case Generator)"

NEW:
"Select 3 MVP AI agents (BAConsultant AI Agent, QAConsultant AI Agent, AutomationConsultant AI Agent)"
```

**Change E3: Epic 2 — FR32-37 References** (same updates as PRD FR changes)

**Change E4: Epic 6 — Story Restructuring**
```
OLD:
"6-1: Web Scraper Agent"
"6-2: Log Reader Agent"
"6-3: Security Tester Agent"
"6-4: Performance Tester Agent"

NEW:
"6-1: AI Log Reader/Summarizer Agent" (renumbered from old 6-2)
"6-2: Security Scanner Orchestrator Agent" (renumbered from old 6-3)
"6-3: Performance/Load Agent" (renumbered from old 6-4)
```
Web Scraper story REMOVED — capability absorbed into AutomationConsultant AI Agent (MVP).

### 4.4 UX Design Changes (`docs/planning/ux-design-specification.md`)

**Change U1: Agent Cards Section** — Update all agent card names and descriptions (10 occurrences)
- Documentation Analyzer → BAConsultant AI Agent
- Manual Tester → QAConsultant AI Agent
- Test Case Generator → QAConsultant AI Agent
- Automation Tester → AutomationConsultant AI Agent

**Change U2: Agent Selection Flow** — Update agent count from 4 MVP to 3 MVP in selection UI flow

### 4.5 Sprint Status Changes (`docs/sprint-status.yaml`)

**Change S1: Epic 6 Stories**
```
OLD:
  6-1-web-scraper-agent: backlog
  6-2-log-reader-agent: backlog
  6-3-security-tester-agent: backlog
  6-4-performance-tester-agent: backlog

NEW:
  6-1-ai-log-reader-summarizer-agent: backlog
  6-2-security-scanner-orchestrator-agent: backlog
  6-3-performance-load-agent: backlog
```

**Change S2: MVP Summary — Story Counts**
```
OLD:
  total_stories: 100
  post_mvp_stories: 8

NEW:
  total_stories: 99
  post_mvp_stories: 7
```
(One story removed: web-scraper-agent from Epic 6)

**Change S3: Metrics — Epic 6**
```
OLD:
  epic-6: { total: 8, backlog: 8, ... }

NEW:
  epic-6: { total: 7, backlog: 7, ... }
```

### 4.6 README Changes (`README.md`)

**Change R1: Agent List** — Update all 8 agent references to new 6 agent structure
**Change R2: Agent Count** — "8 specialized AI agents" → "6 specialized AI agents"
**Change R3: MVP Agent List** — Update to 3 MVP agents
**Change R4: Post-MVP Agent List** — Update to 3 Post-MVP agents

### 4.7 Reports (Low Priority — Historical Context)

**Change RP1:** `docs/reports/implementation-readiness-report-2026-01-22.md` — 2 agent count references
**Change RP2:** `docs/reports/validation-report-architecture-20251211.md` — 1 agent count reference
**Change RP3:** `docs/research/research-market-2025-11-30.md` — 1 agent count reference

**Note:** These are historical reports. Recommend adding a footnote noting the agent restructuring rather than modifying historical content:
> *Note (2026-02-06): Agent structure updated from 8 agents to 6 agents per Sprint Change Proposal. See docs/sprint-change-proposal-2026-02-06.md.*

---

## 5. Implementation Handoff

### Change Scope Classification: MAJOR

This is a **Major** scope change requiring PM and Architect involvement:
- Affects core product definition (PRD agent structure)
- Touches 9+ documents across all planning artifacts
- Introduces expanded agent capabilities
- Restructures MVP/Post-MVP agent boundary
- Requires careful consistency across all documents

### Handoff Plan

| Responsibility | Agent | Documents | Priority |
|---------------|-------|-----------|----------|
| PRD Updates (FR32-37, MVP scope, Executive Summary, Growth Features) | **PM Agent (John)** | `prd.md` | P0 — Do First |
| Architecture Updates (agent counts, SWOT, system design) | **Architect Agent (Winston)** | `architecture.md` | P1 — After PRD |
| Epics Updates (Epic 2 agent refs, Epic 6 restructure) | **PM Agent (John)** | `epics.md` | P1 — After PRD |
| Sprint Status Updates (Epic 6 stories, counts) | **SM Agent (Bob)** | `sprint-status.yaml` | P1 — After Epics |
| UX Design Updates (Agent Cards, selection flow) | **UX-Designer Agent (Sally)** | `ux-design-specification.md` | P2 — After PRD |
| README Updates | **Any Agent** | `README.md` | P2 |
| Report Footnotes | **Any Agent** | `reports/*.md`, `research/*.md` | P3 — Low priority |

### Recommended Execution Order

1. **PRD first** — This is the source of truth. All other documents derive from it.
2. **Architecture** — Must align with updated PRD.
3. **Epics** — Must reflect updated PRD FRs and agent structure.
4. **Sprint Status** — Must match epics restructuring.
5. **UX Design** — Agent card descriptions and selection flow.
6. **README** — Public-facing summary.
7. **Reports** — Historical footnotes.

### Success Criteria

- [ ] All 85+ old agent references updated across 9 documents
- [ ] Agent count consistently "6" (not "8") everywhere
- [ ] MVP agents consistently listed as: BAConsultant, QAConsultant, AutomationConsultant
- [ ] Post-MVP agents consistently listed as: AI Log Reader/Summarizer, Security Scanner Orchestrator, Performance/Load Agent
- [ ] FR32-37 reflect expanded capabilities from research docs
- [ ] Epic 6 restructured (web-scraper removed, 3 post-MVP stories properly named)
- [ ] Sprint status story counts updated
- [ ] No orphaned references to old agent names
- [ ] Cross-document consistency validated

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Missed old agent reference in a document | Medium | Low | Grep search for old names after all updates complete |
| Inconsistency between documents | Medium | Medium | Execute updates in dependency order (PRD → Arch → Epics → Status) |
| FR capability scope creep | Low | Medium | Stick to research doc definitions — no speculative additions |
| Sprint timeline impact | Very Low | Low | Document-only changes, no code impact, parallel with Epic 0 work |

---

*Sprint Change Proposal generated by PM Agent (John) via Correct Course Workflow.*
*Next Step: User approval required before implementation begins.*
