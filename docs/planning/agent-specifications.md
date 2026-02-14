# QUALISYS — AI Agent Specifications & Workflow Architecture

**Product:** QUALISYS — AI System Quality Assurance Platform
**Version:** 1.0
**Date:** 2026-02-06
**Status:** Approved (Aligned with PRD FR32–FR37, Architecture, Epics, and Improvement Research)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Agent Inventory](#2-agent-inventory)
3. [Agent 1 — BAConsultant AI Agent](#3-agent-1--baconsultant-ai-agent)
4. [Agent 2 — QAConsultant AI Agent](#4-agent-2--qaconsultant-ai-agent)
5. [Agent 3 — AutomationConsultant AI Agent](#5-agent-3--automationconsultant-ai-agent)
6. [Agent 4 — AI Log Reader / Summarizer](#6-agent-4--ai-log-reader--summarizer)
7. [Agent 5 — Security Scanner Orchestrator](#7-agent-5--security-scanner-orchestrator)
8. [Agent 6 — Performance / Load Agent](#8-agent-6--performance--load-agent)
9. [Agent 7 — DatabaseConsultant AI Agent](#9-agent-7--databaseconsultant-ai-agent)
10. [Cross-Agent RBAC Matrix](#10-cross-agent-rbac-matrix)
11. [Human-in-the-Loop Master Reference](#11-human-in-the-loop-master-reference)
12. [Agent Interaction Workflow Diagram](#12-agent-interaction-workflow-diagram)
13. [End-to-End Platform Workflow](#13-end-to-end-platform-workflow)
14. [Governance & Artifact Lifecycle](#14-governance--artifact-lifecycle)
15. [Success Metrics Summary](#14-success-metrics-summary)
16. [Agent Skills Integration (Post-MVP — Epic 7)](#15-agent-skills-integration-post-mvp--epic-7)
17. [Agent Extensibility & Custom Agents (Post-MVP — Epic 6 Phase 3)](#16-agent-extensibility--custom-agents-post-mvp--epic-6-phase-3)

---

## 1. Executive Summary

QUALISYS deploys **7 specialized AI agents** organized into two implementation tiers:

| Tier | Agents | Timeline |
|------|--------|----------|
| **MVP** (Epics 0-5) | BAConsultant AI Agent, QAConsultant AI Agent, AutomationConsultant AI Agent | Sprints 0-5 |
| **Post-MVP** (Epic 6) | AI Log Reader/Summarizer, Security Scanner Orchestrator, Performance/Load Agent, DatabaseConsultant AI Agent | Growth Phase |

**Core Design Principles** (from Research Document 2026-02-03):

1. **Human-in-the-loop at every critical stage** — No agent can self-approve
2. **Clear separation of responsibilities** — Zero overlap between agents
3. **Domain-agnostic by design** — Finance, healthcare, e-commerce, SaaS
4. **Governance-first, automation-second** — Approval gates enforce quality
5. **Manual-testing-friendly** — Augments humans, never replaces them

**Sequential Agent Chain (Dual-Review Gate on User Stories):**

```
Requirements → BAConsultant → QAConsultant → AutomationConsultant → Execution
                     ↓              ↓                  ↓
               User Stories    Test Cases         Test Scripts
                     ↓              ↓                  ↓
              Internal Review  Human Approval    Human Approval
                     ↓
              Client Review
                     ↓
              Released to QA
```

> **Critical Rule:** User stories require TWO sequential approvals before release to QAConsultant:
> 1. **Internal Team Review** — BA/QA/PM reviews for quality, completeness, and alignment
> 2. **Client Review** — Client stakeholder reviews for business intent and acceptance
> Only after BOTH reviews mark the story as "Approved" does it become available downstream.

---

## 2. Agent Inventory

| # | Agent Name | PRD Reference | Role Summary | Phase |
|---|-----------|---------------|-------------|-------|
| 1 | **BAConsultant AI Agent** | FR32 | Requirements analysis → test-ready user stories | MVP |
| 2 | **QAConsultant AI Agent** | FR33, FR34, FR36 | Test strategy, manual checklists, BDD scenarios, sprint readiness | MVP |
| 3 | **AutomationConsultant AI Agent** | FR35, FR37 | Automated scripts, framework architecture, self-healing, DOM discovery | MVP |
| 4 | **AI Log Reader/Summarizer** | Epic 6, Story 6-1 | Log analysis, error pattern detection, negative test generation | Post-MVP |
| 5 | **Security Scanner Orchestrator** | Epic 6, Story 6-2 | Vulnerability scanning, OWASP Top 10, security test generation | Post-MVP |
| 6 | **Performance/Load Agent** | Epic 6, Story 6-3 | Load/stress testing, bottleneck identification, SLA validation | Post-MVP |
| 7 | **DatabaseConsultant AI Agent** | Epic 6, Story 6-8 | Schema validation, data integrity, ETL validation, DB performance profiling | Post-MVP |

---

## 3. Agent 1 — BAConsultant AI Agent

### 3.1 Mission

Transform unstructured and structured client inputs (requirements documents, RFPs, specifications, meeting notes) into **client-approved, high-quality, test-ready user stories** with comprehensive traceability and quality validation.

> "First line of intelligence" — ensures requirements are complete, unambiguous, and ready for downstream QA and automation agents.

**PRD Reference:** FR32 — *BAConsultant AI Agent analyzes requirements, performs gap/ambiguity detection, and generates requirements-to-test coverage matrix with user story quality scoring.*

### 3.2 Responsibilities

| # | Responsibility | Description |
|---|---------------|-------------|
| R1 | **Requirements Extraction & Analysis** | Parse PRDs, SRS, RFPs, meeting notes; extract FRs, NFRs, business rules, constraints, dependencies |
| R2 | **Gap, Ambiguity & Assumption Detection** | Flag incomplete requirements, ambiguous language ("fast", "user-friendly"), conflicting requirements, missing NFRs |
| R3 | **User Story Creation** | Generate properly formatted stories (As a [role]…) with acceptance criteria, edge cases, traceability |
| R4 | **Quality Scoring** | Score each story across 8 dimensions (40-point scale); minimum pass threshold: 32/40 |
| R5 | **Domain Adaptation** | Adapt analysis for domain context (finance, healthcare, e-commerce); apply industry best practices |
| R6 | **AI-Specific Requirement Identification** | Identify AI/ML requirements (bias detection, drift, explainability, non-deterministic behavior) |
| R7 | **Edge Case & Negative Scenario Identification** | Generate boundary values, error conditions, security-relevant edge cases |
| R8 | **Requirement Traceability** | Maintain bi-directional mappings: requirement → story → tests |
| R9 | **Review & Approval Support** | Provide rationale for stories, track approval gates, support human review workflows |

### 3.3 Inputs

| Input Type | Formats | Source |
|-----------|---------|--------|
| Requirements Documents | PDF, DOCX, Markdown, CSV/Excel, Plain Text | User upload |
| Project Management | JIRA issues, Confluence pages | MCP server integration |
| Communication | Meeting notes, emails, Slack threads | User upload |
| Code | GitHub README files, API docs | Repository connection |
| Specifications | JSON, OpenAPI/Swagger, XML | User upload |

**Constraints:** Up to 1,000 pages, 100MB total per analysis session; English primary language.

### 3.4 Outputs

#### 3.4.1 User Story Document (JSON + Markdown)

```
Story Structure:
├── Title
├── Persona / Actor
├── Business Intent
├── User Story Statement ("As a [role], I want to [action], so that [benefit]")
├── Functional Flow (step-by-step user journey)
├── Acceptance Criteria (5-8 specific, testable criteria)
├── Edge Cases & Negative Scenarios
├── Non-Functional Requirements (performance, security, usability)
├── Dependencies (blockers, related stories)
├── AI-Specific Notes (if applicable)
├── Traceability References (back to source requirements)
└── Quality Score (0-40 points)
```

#### 3.4.2 Requirements-to-Test Coverage Matrix

Cross-reference: Requirements → Generated Stories → Estimated Test Cases. Identifies coverage gaps (requirements without stories).

#### 3.4.3 Quality Score Report

| Dimension | Max Score | Description |
|-----------|-----------|-------------|
| Clarity | 5 | Is the story unambiguous? |
| Completeness | 5 | Includes acceptance criteria, edge cases? |
| Business Value | 5 | Provides customer value? |
| Testability | 5 | Can be tested objectively? |
| Acceptance Criteria Quality | 5 | Criteria specific and measurable? |
| Edge/Negative Coverage | 5 | Edge cases and negative paths covered? |
| Non-Functional Coverage | 5 | Performance, security, compliance included? |
| Traceability | 5 | Clear link to source requirement? |
| **Total** | **40** | **Minimum pass: 32 (80%)** |

#### 3.4.4 Gap Analysis Report

Severity-ranked list of identified gaps with suggested remediation.

#### 3.4.5 Assumption & Risk Register

Explicit assumptions, flagged risks, recommended clarifications.

### 3.5 RBAC — Accessibility Levels

| Persona | Access Level | Can Trigger | Can Approve (Internal) | Can Approve (Client) | Can View |
|---------|-------------|-------------|------------------------|----------------------|----------|
| **Owner/Admin** | Full | Yes | Yes | No (internal role) | Yes |
| **PM/CSM** | Full | Yes | Yes | No (internal role) | Yes |
| **Client Stakeholder** | Review + Approve | No | No | Yes (Review #2) | Yes (assigned stories) |
| **QA-Automation** | Read-only outputs | No | Yes (internal review) | No | Yes (client-approved stories only) |
| **QA-Manual** | Read-only outputs | No | No | No | Yes (client-approved stories only) |
| **Dev** | No access | No | No | No | No |
| **Viewer** | No access | No | No | No | No |

### 3.6 Human-in-the-Loop Scenarios

| # | Scenario | Trigger | Who Decides | Mandatory? | Decision Options |
|---|---------|---------|-------------|-----------|-----------------|
| H1 | **Internal Team Review** | Agent generates user stories | PM, BA Lead, or QA-Automation (internal team) | **Yes** | Internal Review Done / Request Changes / Reject |
| H2 | **Client Review & Approval** | Internal team marks story as "Internal Review Done" | Client Stakeholder (product owner, business sponsor) | **Yes** | Client Approved / Request Changes / Reject |
| H3 | **Quality Score Below Threshold** | Story scores < 32/40 | PM or Senior QA (internal) | Conditional | Approve with risk / Request improvements / Reject |
| H4 | **Critical Gap Detected** | Security or compliance requirements missing | PM or Architect (internal) | Conditional | Request client clarification / Make assumptions / Defer |
| H5 | **Assumption Validation** | Agent makes explicit assumptions | PM or SME (internal/client) | Conditional | Validate / Correct / Flag as risky |

**Key Rule — Dual-Review Gate:** User stories require **TWO sequential mandatory approvals** before release to QAConsultant:

1. **Internal Team Review (H1)** — The internal BA/QA/PM team reviews the AI-generated story for quality, completeness, alignment with requirements, and technical accuracy. Status: Draft → Internal Review Done.
2. **Client Review (H2)** — The client stakeholder reviews the story for business intent correctness, acceptance criteria accuracy, and domain alignment. Status: Internal Review Done → Client Approved → Released.

Only stories with **both** "Internal Review Done" AND "Client Approved" status are released to the QAConsultant AI Agent for test case generation. No downstream agent can consume stories that have not passed both review gates.

### 3.7 Job Description

> **BAConsultant AI Agent — Job Description**
>
> **Title:** AI Business Analyst Consultant
> **Reports To:** PM/CSM (functional), Platform Orchestrator (technical)
> **Works With:** QAConsultant AI Agent (downstream), AutomationConsultant AI Agent (indirect downstream)
>
> **Summary:** Serve as the intelligent requirements analyst that transforms raw client documentation into structured, scored, approval-ready user stories. Act as the first quality gate ensuring all requirements are complete, unambiguous, and traceable before entering the test generation pipeline. Stories undergo dual-review (internal team + client) before release to downstream agents.
>
> **Key Accountabilities:**
> - Achieve 90%+ story quality scores (>32/40)
> - Maintain 100% requirement-to-story coverage
> - Detect 95%+ of ambiguous requirements
> - Enable <15 minute internal review cycles and <24 hour client review cycles
> - Deliver 100% traceability from requirements through execution
> - Support dual-review workflow (internal team review + client approval)

---

## 4. Agent 2 — QAConsultant AI Agent

### 4.1 Mission

Ensure **quality validation, manual testing governance, and sprint readiness** based on approved user stories from BAConsultant. Operates in two roles:

1. **Test Consultant** — Designs test strategies, creates manual test cases, generates BDD scenarios, validates coverage
2. **ScrumMaster** — Prepares sprint artifacts, validates data availability, ensures team readiness

> "QA orchestrator" — ensures tests are thoughtfully designed before execution and sprints are properly planned.

**PRD References:**
- FR33 — *QAConsultant AI Agent generates manual test checklists with step-by-step instructions, supporting checklist-driven testing across Smoke, Sanity, Integration, Regression, Usability, and UAT types*
- FR34 — *QAConsultant AI Agent generates exploratory testing prompts, BDD/Gherkin scenarios, negative test cases, boundary condition tests, and domain-aware synthetic test data*
- FR36 — *QAConsultant AI Agent creates test strategy documents, test plans, and validates sprint readiness*

### 4.2 Responsibilities

#### Role 1: Test Consultant

| # | Responsibility | Description |
|---|---------------|-------------|
| R1 | **Test Strategy Creation** | Define approach by application type; determine testing pyramid ratios; identify needed test types |
| R2 | **Test Plan Documentation** | Formal plan: scope, objectives, entry/exit criteria, environment/data requirements |
| R3 | **Manual Test Case Generation** | Step-by-step black-box test cases from stories; realistic, business-oriented with clear expected results |
| R4 | **Checklist-Driven Testing** | Structured checklists for 6 testing types: Smoke, Sanity, Integration, Regression, Usability, UAT |
| R5 | **BDD/Gherkin Scenario Generation** | Feature/scenario format; Given/When/Then steps for automation-ready scenarios |
| R6 | **Negative & Boundary Testing** | Equivalence classes, boundary values, partition-based tests, error condition scenarios |
| R7 | **AI Behavior Validation** | Non-deterministic behavior tests, bias detection scenarios, adversarial test cases |
| R8 | **Domain-Aware Synthetic Test Data** | Realistic, masked test data per domain (finance, healthcare, e-commerce); linked to checklists |
| R9 | **Test Coverage Assurance** | Calculate coverage %; identify gaps; recommend additional tests for edge cases |
| R10 | **Requirement-Test Traceability Matrix** | Requirement → Story → Test Case → Manual/Automated mapping; validate 100% coverage |

#### Role 2: ScrumMaster

| # | Responsibility | Description |
|---|---------------|-------------|
| R11 | **Sprint Readiness Validation** | Verify stories have approved tests, test data provisioned, environment stable, team available |
| R12 | **JIRA/Azure DevOps Data Preparation** | Extract story details, validate fields, format data for QAConsultant processing |
| R13 | **MCP Server Coordination** | Manage JIRA/Azure DevOps connectivity, authentication, payload transformations |
| R14 | **AI Bot Schema Alignment** | Ensure generated tests align with AI bot expectations; validate output formats |
| R15 | **Sprint Lifecycle Support** | Track sprint progress, monitor metrics, support sprint closure activities |

### 4.3 Supported Testing Types

| Testing Type | Purpose | Example | Priority |
|-------------|---------|---------|----------|
| **Smoke** | Critical path validation | Can user log in? | P1 Critical |
| **Sanity** | Feature-specific verification | Can user add items to cart? | P1 High |
| **Integration** | Component interaction | Payment service ↔ checkout flow | P1 High |
| **Regression** | Existing functionality preservation | After redesign, can users still log in? | P2 Medium |
| **Usability** | User experience validation | Is navigation intuitive? | P3 Medium |
| **UAT** | Business stakeholder sign-off | Does this meet PRD requirements? | P1 Critical |

### 4.4 Inputs

| Input Type | Source | Format |
|-----------|--------|--------|
| **Approved User Stories** (Primary) | BAConsultant AI Agent | JSON: Title, Acceptance Criteria, Edge Cases, Dependencies, Quality Score |
| Application Documentation | User upload | OpenAPI/Swagger, DB schemas, wireframes, process flows |
| Testing References | Import | CSV, TestRail exports, existing checklists |
| Domain Context | Project config | Domain type, regulatory requirements (PCI-DSS, HIPAA, GDPR) |
| Test Data Requirements | Stories | Data dependencies, masking requirements, provisioning constraints |
| Environment Info | DevOps | Environment details, configs, auth requirements |

### 4.5 Outputs

#### 4.5.1 Test Strategy Document

Testing approach, pyramid ratios, identified types, resource requirements, timeline, success criteria.

#### 4.5.2 Test Plan Document

Formal scope, objectives, entry/exit criteria, environment/data requirements, risk assessment.

#### 4.5.3 Manual Test Checklists (Per Testing Type)

```
Checklist Item Structure:
├── Test ID: MT-001
├── Title: "User can log in with valid credentials"
├── Testing Type: Smoke / Sanity / Regression / Integration / Usability / UAT
├── Priority: P1 (Critical) / P2 (High) / P3 (Medium) / P4 (Low)
├── Preconditions: "User account exists, not locked, staging environment available"
├── Test Steps:
│   ├── Step 1: Navigate to login page
│   ├── Step 2: Enter valid email address
│   ├── Step 3: Enter correct password
│   └── Step 4: Click "Login" button
├── Expected Results:
│   ├── Step 1: Login page loads successfully
│   ├── Step 2: Email field accepts input without error
│   ├── Step 3: Password field masks characters
│   └── Step 4: User redirected to dashboard
├── Test Data: Email: test.user@example.com, Password: [masked]
├── Notes: "Test with Chrome, Firefox, Safari"
└── Traceability: Story 23 → Acceptance Criteria #2
```

#### 4.5.4 BDD/Gherkin Scenarios

```gherkin
Feature: User Authentication
  Background:
    Given user is on the login page
    And user account "test@example.com" exists

  Scenario: Successful login
    When user enters email "test@example.com"
    And user enters password "correct_password"
    And user clicks "Login"
    Then user is redirected to dashboard

  Scenario: Failed login with invalid password
    When user enters email "test@example.com"
    And user enters password "wrong_password"
    And user clicks "Login"
    Then user sees error "Invalid credentials"
```

#### 4.5.5 Negative Test Cases & Boundary Conditions

Error-condition scenarios, off-by-one values, null/empty input handling, case sensitivity tests.

#### 4.5.6 Domain-Aware Synthetic Test Data

Realistic, masked data per domain: credit card numbers (Luhn-valid), addresses, product SKUs, transaction amounts, dates.

#### 4.5.7 Sprint Readiness Report

Stories with approved tests (%), test data status, environment health, team capacity, risk factors, recommended actions.

### 4.6 RBAC — Accessibility Levels

| Persona | Access Level | Can Trigger | Can Approve | Can Execute Tests |
|---------|-------------|-------------|-------------|-------------------|
| **QA-Manual** | Full (Primary) | No | No | Yes |
| **QA-Automation** | Full | Yes | No | Yes |
| **PM/CSM** | Read + Approval | Yes | Yes | No |
| **Owner/Admin** | Full | Yes | Yes | Yes |
| **Dev** | Read-only | No | No | No |
| **Viewer** | No access | No | No | No |

### 4.7 Human-in-the-Loop Scenarios

| # | Scenario | Trigger | Who Decides | Mandatory? | Decision Options |
|---|---------|---------|-------------|-----------|-----------------|
| H1 | **Test Case Quality Review** | Agent generates test cases | PM or Sr QA | **Yes** | Approve / Request Changes / Reject |
| H2 | **Sprint Readiness Validation** | Agent marks sprint as ready | SM or PM | **Yes** | Sprint starts / Sprint delayed |
| H3 | **Test Data Validation** | Synthetic data generated for regulated domain | Data Steward or Domain Expert | Conditional | Approve / Request changes / Provide real data |
| H4 | **High-Risk Compliance Review** | Tests have compliance implications (HIPAA, PCI) | Compliance Officer | Conditional | Approve / Reject / Modify |

**Key Rule:** Test cases cannot be executed or sent to AutomationConsultant until human approval. Sprint cannot start without sprint readiness sign-off.

### 4.8 Job Description

> **QAConsultant AI Agent — Job Description**
>
> **Title:** AI QA Consultant & Sprint Readiness Coordinator
> **Reports To:** PM/CSM (functional), Platform Orchestrator (technical)
> **Works With:** BAConsultant (upstream), AutomationConsultant (downstream), QA-Manual team (direct)
>
> **Summary:** Serve as the dual-role QA intelligence that designs comprehensive test strategies from approved user stories and ensures sprint readiness. Bridge the gap between business requirements and executable test artifacts across 6 testing types.
>
> **Key Accountabilities:**
> - Achieve 100% acceptance-criteria-to-test-case coverage
> - Generate executable checklists in <5 min review time per test
> - Maintain 85%+ test case execution success rate
> - Ensure 95%+ sprints start on schedule (readiness validation)
> - Deliver 90%+ BDD scenario automation adoption rate

---

## 5. Agent 3 — AutomationConsultant AI Agent

### 5.1 Mission

Design, generate, maintain, optimize, and execute automated test frameworks and test scripts. Transforms approved manual testing assets and QAConsultant-validated test cases into **scalable, self-healing automation solutions** integrated with CI/CD pipelines and enterprise DevOps ecosystems.

> "Automation engineer co-pilot" — eliminates manual scripting effort, provides self-healing, ensures test stability as applications evolve.

**PRD References:**
- FR35 — *AutomationConsultant AI Agent generates automated test scripts (Playwright, Puppeteer, REST-Assured) with smart locators, supporting multiple framework architectures (POM, Data-Driven, Hybrid)*
- FR37 — *AutomationConsultant AI Agent performs automated DOM crawling, sitemap generation, and coverage gap detection for application discovery*

### 5.2 Responsibilities

| # | Responsibility | Description |
|---|---------------|-------------|
| R1 | **Framework Architecture Design** | Select optimal framework (POM, Screenplay, Data-Driven, Keyword-Driven, Hybrid) based on app type and team |
| R2 | **Automated Script Generation** | Generate production-quality scripts: Playwright, Puppeteer, REST-Assured, Newman, unit test frameworks |
| R3 | **Automation Suite Management** | Organize tests into suites: Smoke (critical-path, <5min), Sanity, Regression (full coverage), Integration |
| R4 | **Self-Healing Engine** | Locator healing (CSS→XPath→text→ARIA fallback), workflow adaptation, API schema adaptation, runtime correction |
| R5 | **Root Cause Failure Analysis** | Analyze failures: element not found → selector fix; assertion failed → data fix; timeout → wait condition |
| R6 | **DOM & Application Discovery** | Automated crawling, sitemap generation, page inventory metadata, coverage gap detection |
| R7 | **CI/CD Integration** | Jenkins, GitHub Actions, Azure DevOps, CircleCI; trigger-on-commit, PR comments, merge gates |
| R8 | **Cross-Browser Execution** | Chromium, Firefox, WebKit (Safari), Edge; parallel execution across browsers |
| R9 | **Containerized Execution** | OCI containers (Docker/Podman), Kubernetes HPA, pre-warmed container pool |
| R10 | **Automation Readiness Scoring** | Score automation feasibility across 5 dimensions: Stability, Testability, Data Availability, Tooling, CI/CD (1-5 each) |

### 5.3 Supported Technologies

| Category | Technologies |
|----------|-------------|
| **Web UI Testing** | Playwright (primary), Puppeteer (alternative) |
| **API Testing** | REST-Assured, Newman (Postman collections) |
| **Unit Testing** | Jest, Mocha (JS); JUnit, TestNG (Java); pytest, unittest (Python) |
| **Load Testing** | k6, Locust |
| **Languages** | Python, JavaScript/TypeScript, Java, .NET (C#) |
| **CI/CD** | GitHub Actions, Jenkins, Azure DevOps, CircleCI |
| **Containers** | Docker, Podman, Kubernetes (EKS) |

### 5.4 Framework Architectures

| Framework | Best For | Description |
|-----------|----------|-------------|
| **Page Object Model (POM)** | UI-heavy apps, frequent UI changes | Separates page UI definitions from test logic; centralized locator management |
| **Screenplay Pattern** | Business-domain-focused, stakeholder reviews | Higher-level abstraction: actors, tasks, interactions; business-aligned language |
| **Data-Driven** | Boundary testing, regression with multiple scenarios | Single test script, multiple data sets (CSV/JSON) |
| **Keyword-Driven** | Low-code environments, citizen testers | Reusable keywords (navigateTo, enterText, clickButton) |
| **Hybrid** | Large-scale enterprise applications | Combines POM + Data-Driven + Keywords for maximum flexibility |

### 5.5 Self-Healing Engine Detail

```
Failure Detected
    ↓
┌─────────────────────────────────────┐
│ 1. Try Primary Selector (CSS)       │ → Success? → Continue Test
│ 2. Try Fallback 1 (XPath)          │ → Success? → Propose Fix
│ 3. Try Fallback 2 (Text Anchor)    │ → Success? → Propose Fix
│ 4. Try Fallback 3 (ARIA Label)     │ → Success? → Propose Fix
│ 5. All Failed → Root Cause Analysis │ → Human Investigation
└─────────────────────────────────────┘
    ↓
Confidence Score Assigned (0-100%)
    ↓
┌──────────────────────────────────────────┐
│ Staging: Auto-approve if ≥85% confidence │
│ Production: ALWAYS require human approval│
└──────────────────────────────────────────┘
```

### 5.6 Automation Readiness Scoring Model

Before automating any test case, the agent scores readiness:

| Dimension | Score (1-5) | Description |
|-----------|-------------|-------------|
| Application Stability | 1-5 | How stable is the application UI/API? |
| Testability | 1-5 | Can the application be tested programmatically? |
| Data Availability | 1-5 | Is test data available and provisioned? |
| Tooling Compatibility | 1-5 | Do the tools support this application type? |
| CI/CD Integration | 1-5 | Is CI/CD pipeline ready for test execution? |
| **Aggregate** | **5-25** | **Minimum threshold: 15/25 for automation** |

### 5.7 Agent Capability Maturity Model

The agent evolves through 5 maturity levels:

| Level | Name | Description |
|-------|------|-------------|
| 1 | **Assisted Automation** | Agent generates scripts from explicit instructions; human reviews every script |
| 2 | **Guided Automation** | Agent selects frameworks and patterns; human approves strategy |
| 3 | **Intelligent Automation** | Agent self-heals failed tests; human approves fixes |
| 4 | **Autonomous Optimization** | Agent optimizes suites, identifies flaky tests, suggests improvements |
| 5 | **Self-Evolving Agent** | Agent learns from execution history; predictive test selection |

**MVP Target:** Level 2-3 (Guided to Intelligent)

### 5.8 Inputs

| Input Type | Source | Format |
|-----------|--------|--------|
| **Approved Test Cases** (Primary) | QAConsultant AI Agent | JSON checklists, BDD/Gherkin scenarios, coverage matrix |
| Application URL | Project config | URL for DOM crawling |
| GitHub Repository | Project connection | Read-only access for code analysis |
| API Specifications | User upload | OpenAPI/Swagger JSON |
| CI/CD Platform Config | DevOps setup | Jenkins, GitHub Actions, Azure DevOps credentials |
| Browser Preferences | Project config | Chromium, Firefox, WebKit, Edge selection |
| Execution Preferences | Project config | Headless/headful, timeout, retry strategy |

### 5.9 Outputs

| Output | Format | Description |
|--------|--------|-------------|
| **Automated Test Scripts** | JS/TS (Playwright/Puppeteer), Java (REST-Assured) | Production-quality, executable scripts |
| **Framework Blueprint** | Directory structure + config files | Recommended project structure (POM, pages, specs, fixtures) |
| **CI/CD Configuration** | YAML (GitHub Actions/Azure DevOps), Groovy (Jenkins) | Pipeline definitions with test triggers |
| **Automation Suite Inventory** | JSON | Suite definitions: name, test count, runtime, schedule, browsers |
| **Self-Healing Config** | JSON | Selector fallback chains, healing rules, confidence thresholds |
| **Test Execution Reports** | JSON + HTML | Summary (passed/failed/skipped), screenshots, healing suggestions |
| **Application Sitemap** | JSON + visual | Discovered pages, forms, inputs, buttons, dynamic content |
| **Coverage Gap Report** | Markdown | Pages/flows without tests, recommended additional tests |

### 5.10 RBAC — Accessibility Levels

| Persona | Access Level | Can Trigger | Can Approve Scripts | Can Execute | Can Approve Self-Healing |
|---------|-------------|-------------|---------------------|-------------|--------------------------|
| **QA-Automation** | Full (Primary) | Yes | Yes | Yes | Yes |
| **Owner/Admin** | Full | Yes | Yes | Yes | Yes |
| **Dev** | Execute only | No | No | Yes (on-demand) | No |
| **PM/CSM** | Read-only | No | No | No | Yes (production) |
| **QA-Manual** | No access | No | No | No | No |
| **Viewer** | No access | No | No | No | No |

### 5.11 Human-in-the-Loop Scenarios

| # | Scenario | Trigger | Who Decides | Mandatory? | Decision Options |
|---|---------|---------|-------------|-----------|-----------------|
| H1 | **Framework Architecture Approval** | Agent proposes framework design | QA-Automation Lead or Architect | **Yes** | Approve / Request changes / Propose alternative |
| H2 | **Script Generation Validation** | Agent generates test scripts | QA-Automation Engineer | **Yes** | Approve / Request changes / Reject |
| H3 | **Self-Healing Fix (Staging)** | Fix proposed with ≥85% confidence | QA-Automation | Optional | Auto-approve ≥85% / Override |
| H4 | **Self-Healing Fix (Production)** | Any fix proposed for production tests | QA-Automation + PM | **Yes** | Approve fix / Modify / Reject & manual fix |
| H5 | **CI/CD Integration Authorization** | Agent configures pipeline integration | DevOps or Owner/Admin | **Yes** | Authorize / Request changes / Reject |
| H6 | **Automation Readiness Gate** | Test case readiness score < 15/25 | QA-Automation Lead | Conditional | Approve anyway / Defer automation / Request improvements |

**Key Rule:** Scripts cannot enter CI/CD pipeline without human approval. Production self-healing always requires explicit approval.

### 5.12 Job Description

> **AutomationConsultant AI Agent — Job Description**
>
> **Title:** AI Automation Engineering Consultant
> **Reports To:** QA-Automation Lead (functional), Platform Orchestrator (technical)
> **Works With:** QAConsultant (upstream), CI/CD Infrastructure (downstream), Self-Healing Engine (internal)
>
> **Summary:** Serve as the intelligent automation engineer that transforms approved test cases into scalable, self-healing automation frameworks. Eliminate manual scripting effort, integrate with CI/CD pipelines, and ensure test stability through intelligent self-healing.
>
> **Key Accountabilities:**
> - Achieve 95%+ script reliability on first execution
> - Maintain 80%+ automation coverage of manual tests
> - Deliver 80%+ self-healing success rate
> - Reduce regression cycle time by 80%
> - Ensure <10% false failures from brittle locators

---

## 6. Agent 4 — AI Log Reader / Summarizer

### 6.1 Mission

Analyze application logs and test execution logs to identify error patterns, recurring failures, and performance anomalies. Generate targeted negative test cases based on actual error patterns observed in production and testing environments.

**Status:** Post-MVP (Epic 6, Story 6-1)

### 6.2 Responsibilities

| # | Responsibility | Description |
|---|---------------|-------------|
| R1 | **Log Ingestion** | Ingest application logs (error, API, performance) from files and aggregation services |
| R2 | **Error Pattern Detection** | Identify recurring error patterns (e.g., "Connection timeout" 500x/day) |
| R3 | **Trend Analysis** | Detect error rate trends (increasing/decreasing) over time |
| R4 | **Negative Test Generation** | Generate targeted test scenarios for each identified error pattern |
| R5 | **Root Cause Hypothesis** | Suggest probable causes for error patterns |
| R6 | **Stakeholder Summaries** | Summarize log insights for non-technical stakeholders |

### 6.3 Inputs

| Input | Format | Source |
|-------|--------|--------|
| Application log files | .log, JSON logs, structured text | Direct upload |
| Log aggregation feeds | ELK Stack, Splunk, DataDog connections | Integration |
| Test execution logs | QUALISYS execution output | Internal |
| Performance metrics | Prometheus, Grafana exports | Integration |

### 6.4 Outputs

| Output | Description |
|--------|-------------|
| **Error Pattern Report** | Top N patterns: frequency, severity, first seen, trend |
| **Negative Test Cases** | Targeted scenarios per pattern ("Simulate slow DB, verify timeout handling") |
| **Trend Analysis Dashboard** | Error rate visualizations over time |
| **Root Cause Hypotheses** | Suggested causes with confidence levels |

### 6.5 RBAC

| Persona | Access Level |
|---------|-------------|
| **Owner/Admin** | Full |
| **PM/CSM** | Full (summaries, reports) |
| **QA-Automation** | Full (patterns, generated tests) |
| **Dev** | Full (root cause, patterns) |
| **QA-Manual** | Read-only (summaries) |
| **Viewer** | Read-only (dashboards) |

### 6.6 Human-in-the-Loop Scenarios

| # | Scenario | Who Decides | Mandatory? |
|---|---------|-------------|-----------|
| H1 | **Pattern Accuracy Review** | Dev or QA-Automation | **Yes** — confirm patterns are real, not noise |
| H2 | **Generated Test Approval** | QA-Automation | **Yes** — before tests enter execution |
| H3 | **Root Cause Investigation** | Dev team | Conditional — agent provides hypotheses, human validates |

### 6.7 Job Description

> **Title:** AI Log Analysis & Pattern Intelligence Agent
> **Summary:** Analyze production and test execution logs to surface error patterns, detect trends, and automatically generate targeted negative test cases. Bridge the gap between production observability and test coverage.

---

## 7. Agent 5 — Security Scanner Orchestrator

### 7.1 Mission

Coordinate automated security vulnerability scanning and generate security-focused test cases. Identify OWASP Top 10 vulnerabilities and create targeted security tests for compliance validation.

**Status:** Post-MVP (Epic 6, Story 6-2)

### 7.2 Responsibilities

| # | Responsibility | Description |
|---|---------------|-------------|
| R1 | **Vulnerability Scanning** | Scan applications for OWASP Top 10 (SQL injection, XSS, CSRF, insecure auth) |
| R2 | **Security Test Generation** | Generate targeted security test cases per vulnerability |
| R3 | **Compliance Test Suites** | Create tests validating HIPAA, PCI-DSS, GDPR compliance |
| R4 | **Tool Orchestration** | Integrate with OWASP ZAP, Snyk, Semgrep, Bandit |
| R5 | **Remediation Recommendations** | Suggest fixes for identified vulnerabilities |
| R6 | **Security Posture Reporting** | Summary dashboards: vulnerability count, severity distribution, trend |

### 7.3 Inputs

| Input | Format | Source |
|-------|--------|--------|
| Application URL | URL | Project config (authenticated scanning supported) |
| API Specifications | OpenAPI/Swagger | User upload |
| Authentication Credentials | Secure vault | Project config |
| Compliance Requirements | Config | HIPAA, PCI-DSS, GDPR flags |
| Source Code | GitHub repository | Read-only connection |

### 7.4 Outputs

| Output | Description |
|--------|-------------|
| **Vulnerability Report** | Identified vulnerabilities: severity, location, evidence |
| **Security Test Cases** | Generated tests per vulnerability (e.g., SQL injection payloads) |
| **Compliance Test Suite** | Regulatory validation tests |
| **Remediation Guide** | Fix recommendations with code examples |

### 7.5 RBAC

| Persona | Access Level |
|---------|-------------|
| **Owner/Admin** | Full |
| **QA-Automation** | Full (scans, generated tests) |
| **Dev** | Read + Execute (vulnerability reports, fix recommendations) |
| **PM/CSM** | Read-only (summary reports, compliance status) |
| **QA-Manual** | No access |
| **Viewer** | No access |

### 7.6 Human-in-the-Loop Scenarios

| # | Scenario | Who Decides | Mandatory? |
|---|---------|-------------|-----------|
| H1 | **Vulnerability Review** | Security team | **Yes** — confirm findings are real, not false positives |
| H2 | **Security Test Approval** | Security team or QA-Automation | **Yes** — before execution (destructive tests possible) |
| H3 | **Remediation Validation** | Dev team | Conditional — verify fix doesn't break functionality |
| H4 | **Compliance Sign-Off** | Compliance Officer | **Yes** — for regulated environments |

### 7.7 Job Description

> **Title:** AI Security Scanning & Vulnerability Intelligence Agent
> **Summary:** Orchestrate automated security scanning across OWASP Top 10 vectors, generate targeted security test cases, and validate compliance posture. Act as the security quality gate ensuring applications meet security standards before release.

---

## 8. Agent 6 — Performance / Load Agent

### 8.1 Mission

Generate load/stress test scripts, identify performance bottlenecks, validate applications meet performance targets (SLA compliance), and recommend optimizations.

**Status:** Post-MVP (Epic 6, Story 6-3)

### 8.2 Responsibilities

| # | Responsibility | Description |
|---|---------------|-------------|
| R1 | **Load Test Generation** | Generate k6 scripts, JMeter configurations, Locust scenarios |
| R2 | **User Load Simulation** | Simulate 1 / 100 / 1,000 / 10,000 concurrent users with configurable ramp-up |
| R3 | **Performance Measurement** | Capture response time (P50/P95/P99), throughput, error rate, resource utilization |
| R4 | **Bottleneck Identification** | Identify slowest endpoints, highest resource consumers under load |
| R5 | **SLA Validation** | Verify performance targets are met (response time <2s, error rate <0.1%) |
| R6 | **Optimization Recommendations** | Suggest caching, query optimization, scaling, architecture improvements |

### 8.3 Inputs

| Input | Format | Source |
|-------|--------|--------|
| Critical User Flows | Flow definitions (login, checkout, search) | Project config |
| Performance Targets | SLA thresholds (response time, throughput, error rate) | Project config |
| Load Profiles | Concurrent users, ramp-up duration, steady-state period | User config |
| Environment Details | AWS / on-premise, resource specs | Infrastructure config |
| Application Endpoints | URLs, API routes | App discovery or manual |

### 8.4 Outputs

| Output | Description |
|--------|-------------|
| **Load Test Scripts** | k6, JMeter, Locust configurations ready to execute |
| **Performance Test Suites** | Organized by flow: smoke load, standard load, stress, spike |
| **Bottleneck Report** | Slowest endpoints, resource saturation points |
| **SLA Validation Report** | Target vs actual for each SLA metric (pass/fail) |
| **Optimization Recommendations** | Actionable suggestions ranked by impact |

### 8.5 RBAC

| Persona | Access Level |
|---------|-------------|
| **Owner/Admin** | Full |
| **QA-Automation** | Full (scripts, execution, reports) |
| **Dev** | Full (bottleneck reports, optimization recs) |
| **PM/CSM** | Read-only (SLA reports, dashboards) |
| **QA-Manual** | No access |
| **Viewer** | Read-only (dashboards) |

### 8.6 Human-in-the-Loop Scenarios

| # | Scenario | Who Decides | Mandatory? |
|---|---------|-------------|-----------|
| H1 | **Performance Target Review** | PM or Architect | **Yes** — confirm SLA targets are realistic |
| H2 | **Load Profile Approval** | QA-Automation or DevOps | **Yes** — prevent accidental DDoS of staging/production |
| H3 | **Bottleneck Validation** | Dev team | Conditional — confirm bottleneck root cause |
| H4 | **Optimization Sign-Off** | Architect or Dev Lead | Conditional — validate recommendations before implementation |

### 8.7 Job Description

> **Title:** AI Performance Engineering & Load Testing Agent
> **Summary:** Generate intelligent load test scenarios, identify performance bottlenecks under realistic user loads, and validate SLA compliance. Enable proactive performance engineering by surfacing issues before they impact production users.

---

## 9. Agent 7 — DatabaseConsultant AI Agent

### 9.1 Mission

Ensure data integrity, schema safety, ETL validation, and database performance assurance within the QUALISYS platform. Acts as the intelligent database governance layer — validating migrations, detecting integrity violations, profiling query performance, and integrating with CI/CD pipelines for automated database quality gates.

**Status:** Post-MVP (Epic 6, Story 6-8)

### 9.2 Responsibilities

| # | Responsibility | Description |
|---|---------------|-------------|
| R1 | **Schema Validation** | Validate migration scripts for breaking changes, backward compatibility, and schema drift detection |
| R2 | **Data Integrity Checks** | Verify primary keys, foreign keys, constraints, referential integrity across tenant schemas |
| R3 | **ETL Validation** | Compare source vs target row counts, checksums, and data transformation correctness |
| R4 | **Database Performance Profiling** | Identify slow queries, missing indexes, query plan regressions, and connection pool saturation |
| R5 | **CI/CD Database Quality Gate** | Block deployments when migration scripts introduce breaking changes or integrity violations |
| R6 | **Risk Scoring** | Assign risk scores (0-100) to database changes based on impact analysis |

### 9.3 Inputs

| Input | Format | Source |
|-------|--------|--------|
| Migration Scripts | SQL files (e.g., `V45__add_index.sql`) | Version control / CI/CD pipeline |
| Database Connection | Connection string (read-only by default) | Secrets Manager / Key Vault |
| ETL Job Results | Source/target table metadata | ETL pipeline completion events |
| Schema Snapshots | DDL exports / pg_dump | Automated or manual trigger |
| Historical Patterns | Previous validation results | RAG Knowledge Base (vector store) |

### 9.4 Outputs

| Output | Description |
|--------|-------------|
| **Schema Diff Report** | Table-level change report (added/removed/modified columns, indexes, constraints) |
| **Data Integrity Report** | PK/FK/constraint violation summary with sample records |
| **ETL Validation Summary** | Source vs target counts, checksum match status, transformation verification |
| **Performance Profile** | Query execution times, index usage, optimization recommendations |
| **Risk Assessment** | Risk score (0-100) with human-readable explanation and approval recommendation |
| **CI/CD Gate Decision** | Pass/fail/pending-approval status for pipeline integration |

### 9.5 RBAC

| Persona | Access Level |
|---------|-------------|
| **Owner/Admin** | Full |
| **QA-Automation** | Full (trigger validations, view reports) |
| **Dev** | Full (schema validation, performance profiling, recommendations) |
| **PM/CSM** | Read-only (risk reports, integrity dashboards) |
| **QA-Manual** | No access |
| **Viewer** | Read-only (dashboards) |

### 9.6 Human-in-the-Loop Scenarios

| # | Scenario | Who Decides | Mandatory? |
|---|---------|-------------|-----------|
| H1 | **Migration Script Approval** | DB Architect or DevOps | **Yes** — no migration deploys without human sign-off |
| H2 | **Risk Score > 70 Escalation** | DB Architect + Dev Lead | **Yes** — high-risk changes require dual approval |
| H3 | **ETL Validation Failure** | QA Lead or Data Engineer | **Yes** — data discrepancies must be investigated |
| H4 | **Performance Regression Review** | Dev team or DBA | Conditional — triggered when query time regresses >50% |
| H5 | **Production Schema Change** | DevOps + DB Architect | **Yes** — production changes always require explicit approval |

### 9.7 Job Description

> **Title:** AI Database Quality Assurance & Governance Agent
> **Summary:** Validate database schema migrations, enforce data integrity across multi-tenant schemas, profile query performance, and integrate with CI/CD pipelines as an automated quality gate. Ensure database changes are safe, performant, and compliant before reaching production. Operates under strict least-privilege access (read-only by default) with SOC 2-ready audit logging.

### 9.8 Integration Points

| Integration | Description |
|-------------|-------------|
| **CI/CD Pipeline** | Triggered on migration script push; blocks deployment on validation failure |
| **QAConsultant AI Agent** | Receives test data requirements; validates test database integrity |
| **AutomationConsultant AI Agent** | Validates database state before/after automated test execution |
| **Monitoring (Prometheus/Grafana)** | Exports query performance metrics to existing dashboards |
| **Security Scanner Orchestrator** | Shares SQL injection vulnerability findings for database hardening |
| **Performance/Load Agent** | Receives database bottleneck data for load test scenario refinement |

### 9.9 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/db/schema/validate` | Validate migration script |
| POST | `/api/v1/db/data/integrity-check` | Run data integrity checks |
| POST | `/api/v1/db/etl/validate` | Validate ETL job results |
| POST | `/api/v1/db/performance/profile` | Profile query performance |
| GET | `/api/v1/db/test-runs/{id}` | Get test run results |
| POST | `/api/v1/db/human-approval` | Submit human approval decision |

### 9.10 Capability Maturity Model

| Level | Name | Capabilities |
|-------|------|-------------|
| 1 | Query Assistant | Basic query validation, syntax checking |
| 2 | Structured Integrity Validator | PK/FK checks, constraint validation, schema diff |
| 3 | CI/CD Governance Layer | Pipeline integration, automated gates, risk scoring |
| 4 | Predictive Risk Intelligence | Historical pattern analysis, anomaly detection, proactive alerts |
| 5 | Autonomous Advisory System | Self-tuning recommendations, cross-cloud intelligence (human-governed) |

---

## 10. Cross-Agent RBAC Matrix

Complete access matrix for all 7 agents across all 6 QUALISYS personas:

| Persona | BAConsultant | QAConsultant | AutomationConsultant | Log Reader | Security Scanner | Performance Agent | DatabaseConsultant |
|---------|-------------|-------------|---------------------|------------|-----------------|-------------------|--------------------|
| **Owner/Admin** | Full | Full | Full | Full | Full | Full | Full |
| **PM/CSM** | Full | Read + Approve | Read-only | Full | Read-only | Read-only | Read-only |
| **QA-Automation** | Read-only | Full | Full (Primary) | Full | Full | Full | Full |
| **QA-Manual** | Read-only | Full (Primary) | No access | Read-only | No access | No access | No access |
| **Dev** | No access | Read-only | Execute only | Full | Read + Execute | Full | Full |
| **Viewer** | No access | No access | No access | Read-only | No access | Read-only | Read-only |

**Legend:** Full = trigger + approve + view + modify | Read-only = view only | Execute only = run tests, view results | No access = not visible

---

## 10. Human-in-the-Loop Master Reference

Complete catalog of all human intervention points across all agents:

### Mandatory Approvals (Cannot Be Bypassed)

| # | Agent | Gate | Approver | SLA |
|---|-------|------|----------|-----|
| 1 | BAConsultant | Internal Team Review (Review #1) | PM, BA Lead, or QA-Automation (internal) | 24 hours |
| 2 | BAConsultant | Client Review & Approval (Review #2) | Client Stakeholder (product owner) | 48 hours |
| 3 | QAConsultant | Test Case Quality Review | PM or Sr QA | 24 hours |
| 4 | QAConsultant | Sprint Readiness Validation | SM or PM | Before sprint start |
| 5 | AutomationConsultant | Framework Architecture Approval | QA-Automation Lead or Architect | 24 hours |
| 6 | AutomationConsultant | Script Generation Validation | QA-Automation Engineer | 24 hours |
| 7 | AutomationConsultant | Self-Healing Fix (Production) | QA-Automation + PM | Before applying |
| 8 | AutomationConsultant | CI/CD Integration Authorization | DevOps or Owner | 24 hours |
| 9 | Security Scanner | Vulnerability Review | Security team | 24 hours |
| 10 | Security Scanner | Security Test Approval | Security team | 24 hours |
| 11 | Performance Agent | Load Profile Approval | QA-Automation or DevOps | Before execution |
| 12 | DatabaseConsultant | Migration Script Approval | DB Architect or DevOps | Before deployment |
| 13 | DatabaseConsultant | High-Risk Change Escalation (score >70) | DB Architect + Dev Lead | Before deployment |
| 14 | DatabaseConsultant | ETL Validation Failure | QA Lead or Data Engineer | Before data release |
| 15 | DatabaseConsultant | Production Schema Change | DevOps + DB Architect | Before apply |

### Conditional Approvals (Triggered by Thresholds)

| # | Agent | Gate | Trigger Condition | Approver |
|---|-------|------|-------------------|----------|
| 1 | BAConsultant | Quality Score Review | Story scores < 32/40 | PM or Sr QA |
| 2 | BAConsultant | Critical Gap Escalation | Security/compliance requirements missing | PM or Architect |
| 3 | BAConsultant | Assumption Validation | Agent makes explicit assumptions | PM or SME |
| 4 | QAConsultant | Test Data Validation | Regulated domain (finance, healthcare) | Data Steward |
| 5 | QAConsultant | Compliance Review | Tests have HIPAA/PCI implications | Compliance Officer |
| 6 | AutomationConsultant | Self-Healing Fix (Staging) | Confidence < 85% | QA-Automation |
| 7 | AutomationConsultant | Automation Readiness Gate | Readiness score < 15/25 | QA-Automation Lead |
| 8 | Log Reader | Pattern Accuracy Review | New patterns detected | Dev or QA |
| 9 | Performance Agent | Bottleneck Validation | New bottleneck identified | Dev team |
| 10 | DatabaseConsultant | Performance Regression Review | Query time regresses >50% | Dev team or DBA |

### Governance Rule

**No AI agent can self-approve.** All artifacts follow the lifecycle:

```
Draft → Ready for Review → Review Done → Approved → Released
```

**User Stories have an enhanced dual-review lifecycle:**

```
Draft → Ready for Review → Internal Review Done → Client Review → Client Approved → Released
```

> Stories specifically require both internal team approval AND client stakeholder approval before becoming available to downstream agents (QAConsultant, AutomationConsultant).

---

## 11. Agent Interaction Workflow Diagram

### 11.1 Inter-Agent Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    QUALISYS AGENT INTERACTION MAP                    │
└─────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────┐
                    │  User Uploads   │
                    │  PRD / RFP /    │
                    │  Requirements   │
                    └────────┬────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │   BAConsultant AI Agent       │
              │   ─────────────────────────  │
              │   • Requirements extraction  │
              │   • Gap/ambiguity detection   │
              │   • User story creation       │
              │   • Quality scoring (40pt)    │
              └──────────────┬───────────────┘
                             │
                    ┌────────▼────────┐
                    │ 🔒 REVIEW #1   │
                    │ Internal Team  │
                    │ Reviews Stories │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 🔒 REVIEW #2   │
                    │ Client Approves│
                    │ User Stories   │
                    └────────┬────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │   QAConsultant AI Agent       │
              │   ─────────────────────────  │
              │   • Test strategy & plans     │
              │   • Manual test checklists    │
              │   • BDD/Gherkin scenarios     │
              │   • Negative/boundary tests   │
              │   • Synthetic test data        │
              │   • Sprint readiness           │
              └──────────┬───────┬───────────┘
                         │       │
                ┌────────▼──┐  ┌─▼────────────┐
                │ 🔒 HUMAN  │  │ 🔒 HUMAN     │
                │ Test Case │  │ Sprint Ready  │
                │ Approval  │  │ Validation    │
                └────────┬──┘  └──────────────┘
                         │
              ┌──────────▼───────────────────┐      ┌──────────────────┐
              │ AutomationConsultant AI Agent │      │  QA-Manual Team  │
              │ ───────────────────────────  │      │  ──────────────  │
              │ • Framework architecture      │      │  Execute manual  │
              │ • Script generation           │◄────►│  checklists      │
              │ • Suite management            │      │  Evidence capture│
              │ • Self-healing engine         │      │  Defect filing   │
              │ • DOM discovery               │      └──────────────────┘
              │ • CI/CD integration           │
              └──────────┬───────────────────┘
                         │
                ┌────────▼────────┐
                │  🔒 HUMAN GATE  │
                │  QA-Auto Approves│
                │  Scripts + CI/CD │
                └────────┬────────┘
                         │
              ┌──────────▼───────────────────┐
              │   Test Execution Engine       │
              │   ───────────────────────    │
              │   • Parallel execution        │
              │   • Cross-browser testing     │
              │   • Containerized runners     │
              │   • CI/CD pipeline triggers   │
              └──────────┬───────────────────┘
                         │
                         ▼
              ┌──────────────────────────────┐
              │   Self-Healing Engine         │
              │   ─────────────────────────  │
              │   • Locator healing (4-tier)  │
              │   • Root cause analysis       │
              │   • Confidence scoring        │
              │   • Fix proposals             │
              └──────────┬───────────────────┘
                         │
                ┌────────▼────────┐
                │  🔒 HUMAN GATE  │
                │  Approve Fix    │
                │  (Prod: always) │
                └────────┬────────┘
                         │
                         ▼
              ┌──────────────────────────────┐
              │   Dashboards & Reports        │
              │   ─────────────────────────  │
              │   • PM/CSM: coverage, SLAs    │
              │   • QA: test runs, flaky tests│
              │   • KPIs: velocity, pass rates│
              └──────────────────────────────┘
```

### 11.2 Post-MVP Agent Integration

```
┌──────────────────────────────────────────────────────────────────────┐
│                     POST-MVP AGENT EXTENSIONS                        │
└──────────────────────────────────────────────────────────────────────┘

     Application Logs              Application URL              Critical Flows
          │                              │                            │
          ▼                              ▼                            ▼
┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
│ AI Log Reader/   │        │ Security Scanner │        │ Performance/     │
│ Summarizer       │        │ Orchestrator     │        │ Load Agent       │
│ ────────────     │        │ ────────────     │        │ ────────────     │
│ • Error patterns │        │ • OWASP Top 10   │        │ • Load scripts   │
│ • Trend analysis │        │ • Vuln scanning  │        │ • Bottleneck ID  │
│ • Root cause     │        │ • Compliance     │        │ • SLA validation │
│ • Negative tests │        │ • Security tests │        │ • Optimization   │
└────────┬─────────┘        └────────┬─────────┘        └────────┬─────────┘
         │                           │                            │
         └───────────┬───────────────┴────────────┬───────────────┘
                     │                             │
                     ▼                             ▼
         ┌───────────────────┐         ┌───────────────────┐
         │  🔒 Human Review  │         │  Test Execution    │
         │  & Approval       │         │  Pipeline          │
         └───────────────────┘         └───────────────────┘
```

---

## 12. End-to-End Platform Workflow

### 12.1 Complete QUALISYS Platform Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    QUALISYS END-TO-END PLATFORM WORKFLOW                      │
│                                                                              │
│  "5-Minute Value Moment" — Upload PRD → Get Test Suites                      │
└──────────────────────────────────────────────────────────────────────────────┘

PHASE 1: PROJECT SETUP
══════════════════════

  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  Sign Up │────►│  Create  │────►│ Configure│────►│  Invite  │
  │  / Login │     │  Org     │     │ Project  │     │  Team    │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘
       │                                  │
       │            Personas: Owner/Admin, PM/CSM
       │                                  │
       ▼                                  ▼
  ┌──────────────────────────────────────────────┐
  │  RBAC Assignment (6 Roles)                    │
  │  Owner > PM/CSM > QA-Auto > QA-Manual > Dev > Viewer
  └──────────────────────────────────────────────┘


PHASE 2: INTELLIGENT INGESTION
═══════════════════════════════

  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
  │  📄 Document   │  │  🔗 GitHub     │  │  🌐 DOM        │
  │  Upload        │  │  Repository    │  │  Crawling      │
  │  ────────────  │  │  ────────────  │  │  ────────────  │
  │  PRD, SRS, RFP │  │  Read-only     │  │  Playwright    │
  │  PDF, Word, MD │  │  Routes, APIs  │  │  Pages, Forms  │
  │  CSV, Excel    │  │  Components    │  │  Auth Flows    │
  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
          │                   │                    │
          └───────────┬───────┴────────────────────┘
                      │
                      ▼
          ┌───────────────────────────┐
          │  Embedding Generation      │
          │  ──────────────────────   │
          │  sentence-transformers     │
          │  → pgvector (PostgreSQL)   │
          │  → Semantic search ready   │
          └───────────┬───────────────┘
                      │
                      ▼

PHASE 3: AI AGENT PIPELINE (MVP)
════════════════════════════════

  ┌─────────────────────────────────────────────────────────────────┐
  │  STAGE 1: BAConsultant AI Agent                                  │
  │  ─────────────────────────────                                  │
  │                                                                  │
  │  Inputs:  Parsed documents + embeddings + domain context         │
  │                                                                  │
  │  Processing:                                                     │
  │  ├── Requirements extraction (FRs, NFRs, business rules)         │
  │  ├── Gap & ambiguity detection                                   │
  │  ├── User story creation (per 4.4 structure)                     │
  │  ├── Quality scoring (8 dimensions, 40-point scale)              │
  │  ├── Edge case & negative scenario identification                │
  │  └── Coverage matrix generation                                  │
  │                                                                  │
  │  Outputs:                                                        │
  │  ├── User Stories (structured JSON + MD)                         │
  │  ├── Requirements-to-Test Coverage Matrix                        │
  │  ├── Quality Score Report (per-story breakdown)                  │
  │  ├── Gap Analysis Report (severity-ranked)                       │
  │  └── Assumption & Risk Register                                  │
  │                                                                  │
  │  ┌──────────────────────────────────────────────────┐            │
  │  │  🔒 MANDATORY APPROVAL GATE #1 — Internal Review │            │
  │  │  Who: PM, BA Lead, or QA-Automation (internal)   │            │
  │  │  Action: Review stories for quality & completeness│            │
  │  │  Conditions:                                      │            │
  │  │  • Quality score ≥ 32/40                          │            │
  │  │  • No critical gaps                               │            │
  │  │  • All acceptance criteria present (min 3)        │            │
  │  │  • Traceability link verified                     │            │
  │  │  • Assumptions validated                          │            │
  │  │  Result: Status → "Internal Review Done"          │            │
  │  └──────────────────────────────────────────────────┘            │
  │                                                                  │
  │  ┌──────────────────────────────────────────────────┐            │
  │  │  🔒 MANDATORY APPROVAL GATE #2 — Client Review   │            │
  │  │  Who: Client Stakeholder (product owner, sponsor) │            │
  │  │  Action: Validate business intent & acceptance    │            │
  │  │  Conditions:                                      │            │
  │  │  • Business intent matches client expectations    │            │
  │  │  • Acceptance criteria are correct per domain     │            │
  │  │  • Edge cases align with real-world scenarios     │            │
  │  │  Result: Status → "Client Approved" → "Released"  │            │
  │  └──────────────────────────────────────────────────┘            │
  └──────────────────────────────┬──────────────────────────────────┘
                                 │ Client-Approved Stories
                                 ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  STAGE 2: QAConsultant AI Agent                                  │
  │  ─────────────────────────────                                  │
  │                                                                  │
  │  Inputs:  Approved user stories + domain context + env info      │
  │                                                                  │
  │  Processing (Test Consultant):                                   │
  │  ├── Test strategy creation (approach, pyramid, types needed)    │
  │  ├── Test plan documentation (scope, entry/exit criteria)        │
  │  ├── Manual test checklist generation (6 types)                  │
  │  │   ├── Smoke Testing (critical path, P1)                      │
  │  │   ├── Sanity Testing (feature-specific, P1)                  │
  │  │   ├── Integration Testing (component interaction, P1)        │
  │  │   ├── Regression Testing (existing functionality, P2)        │
  │  │   ├── Usability Testing (UX validation, P3)                  │
  │  │   └── UAT (stakeholder sign-off, P1)                         │
  │  ├── BDD/Gherkin scenario generation                             │
  │  ├── Negative & boundary test cases                              │
  │  ├── Synthetic test data (domain-aware, masked)                  │
  │  └── Coverage matrix validation (100% target)                    │
  │                                                                  │
  │  Processing (ScrumMaster):                                       │
  │  ├── Sprint readiness validation                                 │
  │  ├── JIRA/Azure DevOps data preparation                          │
  │  └── Sprint lifecycle support                                    │
  │                                                                  │
  │  Outputs:                                                        │
  │  ├── Test Strategy Document                                      │
  │  ├── Test Plan Document                                          │
  │  ├── Manual Test Checklists (per type)                           │
  │  ├── BDD/Gherkin Scenarios                                       │
  │  ├── Negative Test Cases                                         │
  │  ├── Synthetic Test Data                                         │
  │  └── Sprint Readiness Report                                     │
  │                                                                  │
  │  ┌──────────────────────────────────────────────────┐            │
  │  │  🔒 MANDATORY APPROVAL GATE (x2)                 │            │
  │  │                                                   │            │
  │  │  Gate A — Test Case Quality                       │            │
  │  │  Who: PM or Sr QA Engineer                        │            │
  │  │  Action: Review test cases, approve/reject         │            │
  │  │                                                   │            │
  │  │  Gate B — Sprint Readiness                        │            │
  │  │  Who: SM or PM                                    │            │
  │  │  Action: Sprint starts / Sprint delayed            │            │
  │  │  Checks: Test cases approved, data provisioned,   │            │
  │  │          environment stable, team available        │            │
  │  └──────────────────────────────────────────────────┘            │
  └──────────────────┬───────────────────┬──────────────────────────┘
                     │                   │
      Approved Tests │                   │ Manual Checklists
                     ▼                   ▼
  ┌──────────────────────────┐  ┌──────────────────────────┐
  │  STAGE 3A:               │  │  STAGE 3B:               │
  │  AutomationConsultant    │  │  Manual Test Execution    │
  │  AI Agent                │  │  ─────────────────────   │
  │  ────────────────────   │  │                           │
  │                          │  │  QA-Manual team executes  │
  │  Processing:             │  │  step-by-step checklists: │
  │  ├── Framework design    │  │  ├── Execute test steps   │
  │  ├── Script generation   │  │  ├── Capture evidence     │
  │  │   ├── Playwright      │  │  │   (screenshots, video) │
  │  │   ├── Puppeteer       │  │  ├── Record pass/fail     │
  │  │   ├── REST-Assured    │  │  ├── File defects → JIRA  │
  │  │   └── Newman          │  │  └── Update traceability  │
  │  ├── Suite organization  │  │                           │
  │  │   ├── Smoke (<5min)   │  │  Evidence captured in     │
  │  │   ├── Sanity          │  │  platform with full       │
  │  │   ├── Regression      │  │  traceability chain.      │
  │  │   └── Integration     │  │                           │
  │  ├── Self-healing config │  └──────────────┬───────────┘
  │  ├── DOM discovery       │                  │
  │  └── CI/CD integration   │                  │
  │                          │                  │
  │  ┌────────────────────┐  │                  │
  │  │ 🔒 APPROVAL GATES  │  │                  │
  │  │ • Framework design  │  │                  │
  │  │ • Script validation │  │                  │
  │  │ • CI/CD auth        │  │                  │
  │  └────────────────────┘  │                  │
  └──────────────┬───────────┘                  │
                 │                               │
                 ▼                               │
  ┌──────────────────────────────────────────────┤
  │  AUTOMATED TEST EXECUTION                    │
  │  ───────────────────────                     │
  │                                              │
  │  ┌─────────────────────────────────────┐     │
  │  │  CI/CD Pipeline Trigger              │     │
  │  │  • On commit/PR (smoke tests)        │     │
  │  │  • Nightly (regression suite)        │     │
  │  │  • On-demand (full suite)            │     │
  │  └───────────────┬─────────────────────┘     │
  │                  │                            │
  │  ┌───────────────▼─────────────────────┐     │
  │  │  Containerized Execution             │     │
  │  │  • Podman/Docker containers          │     │
  │  │  • Kubernetes HPA autoscaling        │     │
  │  │  • Parallel (50+ simultaneous)       │     │
  │  │  • Cross-browser (Chromium/FF/WebKit)│     │
  │  └───────────────┬─────────────────────┘     │
  │                  │                            │
  │        ┌─────────▼──────────┐                 │
  │        │  Test Passes?      │                 │
  │        └──┬─────────────┬───┘                 │
  │       Yes │             │ No                  │
  │           │             ▼                     │
  │           │  ┌────────────────────┐           │
  │           │  │ Self-Healing Engine│           │
  │           │  │ • Try fallback     │           │
  │           │  │   selectors        │           │
  │           │  │ • Confidence score │           │
  │           │  │ • Fix proposal     │           │
  │           │  └────────┬───────────┘           │
  │           │           │                       │
  │           │  ┌────────▼───────────┐           │
  │           │  │ 🔒 APPROVE FIX    │           │
  │           │  │ Staging: auto ≥85% │           │
  │           │  │ Prod: always manual│           │
  │           │  └────────┬───────────┘           │
  │           │           │                       │
  │           ▼           ▼                       │
  │  ┌────────────────────────────────────┐      │
  │  │  Test Results Aggregation           │      │
  │  │  • Pass/fail/skip counts            │      │
  │  │  • Screenshots & videos             │      │
  │  │  • Execution time                   │      │
  │  │  • Healing actions applied          │      │
  │  │  • Coverage metrics                 │      │
  │  └──────────────────┬─────────────────┘      │
  └─────────────────────┼────────────────────────┘
                        │
                        ▼

PHASE 4: REPORTING & VISIBILITY
═══════════════════════════════

  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                  │
  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
  │  │  PM/CSM          │  │  QA Dashboard   │  │  Dev Dashboard  │  │
  │  │  Dashboard       │  │                 │  │                 │  │
  │  │  ─────────────  │  │  ─────────────  │  │  ─────────────  │  │
  │  │  • Project health│  │  • Test runs    │  │  • PR results   │  │
  │  │  • Coverage %    │  │  • Failing tests│  │  • Test triggers│  │
  │  │  • SLA compliance│  │  • Flaky tests  │  │  • Code coverage│  │
  │  │  • Velocity      │  │  • Environment  │  │  • Merge gates  │  │
  │  │  • Defect leakage│  │  • Execution    │  │  • On-demand    │  │
  │  │  • KPI trends    │  │    velocity     │  │    test runs    │  │
  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
  │                                                                  │
  │  ┌─────────────────────────────────────────────────────────────┐ │
  │  │  Enterprise Integrations                                    │ │
  │  │  ─────────────────────                                     │ │
  │  │  JIRA ←→ Bi-directional sync (defects, stories)            │ │
  │  │  TestRail/Testworthy ←→ Import/export test plans            │ │
  │  │  GitHub ←→ PR comments, merge gates, webhooks               │ │
  │  │  Slack/Teams ←→ Notifications, ChatOps commands             │ │
  │  │  PDF Reports → Scheduled stakeholder summaries              │ │
  │  └─────────────────────────────────────────────────────────────┘ │
  │                                                                  │
  └──────────────────────────────────────────────────────────────────┘


PHASE 5: POST-MVP EXTENSIONS (Epic 6)
══════════════════════════════════════

  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
  │  AI Log Reader   │  │  Security        │  │  Performance    │
  │  /Summarizer     │  │  Scanner         │  │  /Load Agent    │
  │  ─────────────  │  │  Orchestrator    │  │  ─────────────  │
  │                  │  │  ─────────────  │  │                  │
  │  App/test logs   │  │  OWASP Top 10   │  │  k6/JMeter/     │
  │  → Error patterns│  │  → Vuln report  │  │  Locust scripts  │
  │  → Negative tests│  │  → Security     │  │  → Bottleneck    │
  │  → Trend analysis│  │    test cases   │  │    reports       │
  │  → Root cause    │  │  → Compliance   │  │  → SLA validation│
  │    hypotheses    │  │    test suites  │  │  → Optimization  │
  └─────────────────┘  └─────────────────┘  └─────────────────┘
          │                     │                      │
          └─────────────────────┼──────────────────────┘
                                │
                                ▼
                  Feeds into MVP agent pipeline
                  (additional test cases → QAConsultant
                   → AutomationConsultant → Execution)
```

### 12.2 Data Transformation Chain

```
┌────────────────────────────────────────────────────────────────────────────┐
│                   ARTIFACT TRANSFORMATION PIPELINE                         │
└────────────────────────────────────────────────────────────────────────────┘

Layer 1: RAW INPUT
─────────────────
  PRD (PDF) ─┬─ SRS (Word) ─┬─ RFP (MD) ─┬─ JIRA Issues ─┬─ Meeting Notes
             │               │             │               │
             └───────────────┴─────────────┴───────────────┘
                                    │
                          Document Parsing + Embedding
                                    │
                                    ▼
Layer 2: STRUCTURED REQUIREMENTS  [BAConsultant]
───────────────────────────────
  User Stories (JSON) ─┬─ Coverage Matrix ─┬─ Quality Scores ─┬─ Gap Report
                       │                   │                  │
              🔒 Internal Team Review Gate (PM/BA/QA)
                       │
              🔒 Client Review & Approval Gate (Client Stakeholder)
                       │
                       ▼
Layer 3: TEST ARTIFACTS  [QAConsultant]
──────────────────────
  Test Strategy ─┬─ Test Plan ─┬─ Manual Checklists ─┬─ BDD Scenarios
                 │             │   (6 types)          │
                 ├─ Negative Tests ─┬─ Synthetic Data ─┤
                 │                  │                   │
              🔒 Human Approval Gate (PM/Sr QA)
                 │                  │
        ┌────────┘                  └────────┐
        ▼                                    ▼
Layer 4a: AUTOMATION  [AutomationConsultant]    Layer 4b: MANUAL EXECUTION
─────────────────────                           ──────────────────────────
  Framework Blueprint ─┬─ Test Scripts          QA-Manual Checklists ─┬─ Evidence
  CI/CD Config         │  (Playwright/etc)      Step Execution        │  Capture
  Suite Inventory      │                        Pass/Fail Recording   │
  Self-Healing Config  │                        Defect Filing → JIRA  │
                       │                                              │
              🔒 Human Approval                                       │
                       │                                              │
                       ▼                                              │
Layer 5: EXECUTION RESULTS                                            │
──────────────────────                                                │
  Test Results ─┬─ Screenshots ─┬─ Self-Healing Actions ──────────────┘
                │               │
                ▼               ▼
Layer 6: BUSINESS INTELLIGENCE
──────────────────────────────
  PM/CSM Dashboards ─┬─ QA Dashboards ─┬─ PDF Reports ─┬─ JIRA Sync
  Coverage Trends     │  Test Velocity   │  Scheduled     │  Defects
  SLA Compliance      │  Flaky Tests     │  Summaries     │  Auto-created
```

---

## 13. Governance & Artifact Lifecycle

### 13.1 Universal Artifact Status Model

**Standard Lifecycle** (Test Cases, Scripts, Reports — single review):

```
  ┌──────────┐         ┌──────────────────┐         ┌─────────────┐
  │  Draft   │────────►│ Ready for Review │────────►│ Review Done │
  │          │         │                  │         │             │
  │ AI Agent │         │ Agent signals    │         │ Human has   │
  │ generated│         │ quality met      │         │ reviewed    │
  └──────────┘         └──────────────────┘         └──────┬──────┘
                                                           │
                                              ┌────────────┼────────────┐
                                              │            │            │
                                              ▼            ▼            ▼
                                        ┌──────────┐ ┌──────────┐ ┌──────────┐
                                        │ Approved │ │ Changes  │ │ Rejected │
                                        │          │ │ Requested│ │          │
                                        │ Human    │ │          │ │ Restart  │
                                        │ sign-off │ │ Rework   │ │ or drop  │
                                        └────┬─────┘ └────┬─────┘ └──────────┘
                                             │            │
                                             │            └──► Back to Draft
                                             ▼
                                        ┌──────────┐
                                        │ Released │
                                        │          │
                                        │ In use by│
                                        │ downstream│
                                        │ agents   │
                                        └────┬─────┘
                                             │
                                             ▼
                                        ┌──────────┐
                                        │ Archived │
                                        │          │
                                        │ History  │
                                        │ preserved│
                                        └──────────┘
```

**User Story Lifecycle** (Dual-Review — internal team + client approval):

```
  ┌──────────┐         ┌──────────────────┐
  │  Draft   │────────►│ Ready for Review │
  │          │         │                  │
  │ BA Agent │         │ Quality score    │
  │ generated│         │ threshold met    │
  └──────────┘         └────────┬─────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │  INTERNAL TEAM REVIEW    │  ◄── Review #1
                   │  (PM, BA Lead, QA-Auto) │
                   └────────────┬────────────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                │
               ▼                ▼                ▼
  ┌────────────────┐  ┌──────────────┐  ┌──────────┐
  │ Internal       │  │ Changes      │  │ Rejected │
  │ Review Done    │  │ Requested    │  │          │
  │                │  │ → Back to    │  │ Restart  │
  │ Passes to      │  │   Draft      │  │ or drop  │
  │ client review  │  └──────────────┘  └──────────┘
  └───────┬────────┘
          │
          ▼
  ┌─────────────────────────┐
  │  CLIENT REVIEW           │  ◄── Review #2
  │  (Client Stakeholder,   │
  │   Product Owner)         │
  └────────────┬────────────┘
               │
  ┌────────────┼────────────────┐
  │            │                │
  ▼            ▼                ▼
┌──────────┐ ┌──────────────┐ ┌──────────┐
│ Client   │ │ Changes      │ │ Rejected │
│ Approved │ │ Requested    │ │          │
│          │ │ → Back to    │ │ Back to  │
│          │ │   Draft      │ │ Draft    │
└────┬─────┘ └──────────────┘ └──────────┘
     │
     ▼
┌──────────┐
│ Released │ ──► Available to QAConsultant AI Agent
│          │
└────┬─────┘
     │
     ▼
┌──────────┐
│ Archived │
└──────────┘
```

> **Note:** Only user stories require the dual-review lifecycle. Test cases, test scripts, and other artifacts use the standard single-review lifecycle above.

### 13.2 Approval Authority Matrix

| Artifact Type | Primary Approver | Secondary Approver | Approval SLA | Escalation Path |
|--------------|-----------------|-------------------|-------------|----------------|
| User Stories (Internal Review) | PM, BA Lead, or QA-Automation | Sr QA | 24 hours | → Owner/Admin |
| User Stories (Client Review) | Client Stakeholder (Product Owner) | Client Sponsor | 48 hours | → PM escalates to client management |
| Test Cases | PM or Sr QA | QA-Automation | 24 hours | → Owner/Admin |
| Sprint Readiness | SM or PM | Owner | Before sprint start | → Owner/Admin |
| Automation Framework | QA-Automation Lead | Architect | 24 hours | → Owner/Admin |
| Test Scripts | QA-Automation Engineer | QA-Automation Lead | 24 hours | → Owner/Admin |
| Self-Healing Fix (Staging) | QA-Automation (auto ≥85%) | Owner (override) | Immediate | N/A |
| Self-Healing Fix (Production) | QA-Automation + PM | Owner | Before applying | → Owner/Admin |
| CI/CD Integration | DevOps Engineer | Owner/Admin | 24 hours | → Owner/Admin |

### 13.3 Agent Trigger Authority

| Agent | Who Can Trigger | When | Frequency |
|-------|----------------|------|-----------|
| BAConsultant | PM, QA-Automation, Owner | New project or PRD change | 1x per project (or on change) |
| QAConsultant | PM, QA-Automation, Owner | After BAConsultant approval | After each story release |
| AutomationConsultant | QA-Automation, Owner | After QAConsultant approval | After each test case release |
| AI Log Reader | QA-Automation, Dev, Owner | On-demand or scheduled | Periodic (daily/weekly) |
| Security Scanner | QA-Automation, Owner | On-demand or pre-release | Per release cycle |
| Performance Agent | QA-Automation, DevOps, Owner | On-demand or pre-release | Per release cycle |

---

## 14. Success Metrics Summary

### 14.1 Per-Agent Metrics

| Agent | Metric | Target | Measurement |
|-------|--------|--------|-------------|
| **BAConsultant** | Story quality score | 90%+ stories > 32/40 | Quality score distribution |
| **BAConsultant** | Requirement coverage | 100% requirements → stories | Coverage matrix |
| **BAConsultant** | Ambiguity detection | 95%+ identified | Comparison with human BA |
| **BAConsultant** | Review cycle time | < 15 min per story | Time-to-approval tracking |
| **QAConsultant** | Test case coverage | 100% criteria → test cases | Traceability matrix |
| **QAConsultant** | Execution efficiency | < 5 min per test case | Execution time tracking |
| **QAConsultant** | Test case quality | 85%+ execute successfully | Success rate tracking |
| **QAConsultant** | Sprint readiness accuracy | 95%+ sprints on time | Sprint metrics |
| **QAConsultant** | BDD scenario adoption | 90%+ used for automation | Cross-agent tracking |
| **AutomationConsultant** | Script reliability | 95%+ pass first run | Per-script success rate |
| **AutomationConsultant** | Automation coverage | 80%+ manual → automated | Coverage ratio analysis |
| **AutomationConsultant** | Self-healing success | 80%+ fixes correct | Post-fix validation |
| **AutomationConsultant** | Regression cycle | 80% time reduction | Pipeline execution time |
| **AutomationConsultant** | Locator robustness | < 10% false failures | Failure root cause analysis |
| **Log Reader** | Pattern detection | 90%+ significant patterns | Validation review |
| **Security Scanner** | Vulnerability coverage | 95%+ OWASP Top 10 | Security audit comparison |
| **Performance Agent** | Bottleneck identification | 100% of issues found | Infrastructure monitoring |

### 14.2 Platform-Level Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| **Time to First Test Suite** | < 10 minutes | From project creation to first generated artifacts |
| **Test Maintenance Reduction** | 70% | Time spent fixing broken tests (before vs after self-healing) |
| **Test Coverage Improvement** | 40% increase | Requirements coverage after 60 days (60% → 85%+) |
| **Cross-Role Adoption** | 3+ personas active | PM + QA-Manual + QA-Automation all using platform weekly |
| **Monthly Retention** | > 85% MoM | Month-over-month paid team retention |
| **Self-Healing Rate** | 80%+ | Test failures auto-fixed without human intervention |

---

## 15. Agent Skills Integration (Post-MVP — Epic 7)

### 15.1 Progressive Disclosure Model

All 7 QUALISYS agents will be retrofitted with Anthropic Agent Skills using a three-level progressive disclosure model that loads only the capability needed for each invocation:

| Level | Content | Token Load | When Loaded |
|-------|---------|-----------|-------------|
| **Level 1 (Metadata)** | Skill name, description, tags | ~50-100 tokens | Always loaded — enables discovery |
| **Level 2 (Instructions)** | Procedural execution steps, patterns | ~500-2,000 tokens | On skill invocation |
| **Level 3 (Resources)** | Templates, examples, reference data | ~500-1,000 tokens | On demand within execution |

### 15.2 Agent-Skill Mapping

| Agent | Skills (3 per agent) | Current Tokens | With Skills | Reduction |
|-------|---------------------|---------------|-------------|-----------|
| **BAConsultant** | Document Parser, Requirements Extractor, Gap Analyzer | ~25,000 | ~6,000 | **76%** |
| **QAConsultant** | Test Strategy Generator, BDD Scenario Writer, Test Data Generator | ~20,000 | ~5,500 | **72%** |
| **AutomationConsultant** | Playwright Script Generator, Selector Optimizer, Self-Healing Analyzer | ~22,000 | ~6,500 | **70%** |
| **DatabaseConsultant** | Schema Validator, ETL Checker, Performance Profiler | ~18,000 | ~5,000 | **72%** |
| **Security Scanner** | Vulnerability Analyzer, OWASP Top 10 Checker, Security Test Generator | ~16,000 | ~5,500 | **66%** |
| **Performance/Load** | Load Test Generator, Bottleneck Identifier, SLA Validator | ~14,000 | ~4,000 | **71%** |
| **AI Log Reader** | Error Pattern Detector, Log Summarizer, Negative Test Generator | ~15,000 | ~4,500 | **70%** |

**Total:** 21 skills across 7 agents | **Aggregate Reduction:** 40-60%

### 15.3 Zero Regression Architecture

Every skill-enabled agent path has a full-context fallback:

```
Skill Invocation Attempt
    ├── Success → Use skill output (40-60% fewer tokens)
    ├── Skill Registry unavailable → Agent runs full-context mode
    ├── Skill Proxy timeout → Agent runs full-context mode
    ├── Claude API error → Retry (3x) → Fall back to full-context
    └── Governance blocks → Queue for approval OR fall back
```

**Critical Rule:** Skills are optimization — never a hard dependency. Agents function identically with skills disabled (FR-SK28).

### 15.4 Skill Governance Extensions

Skill governance extends the existing 15 human-in-the-loop gates:

| Risk Level | Approval | Examples |
|-----------|----------|---------|
| **Low** | Auto-approved | Document Parser, BDD Scenario Writer, Log Summarizer |
| **Medium** | QA-Automation approval | Self-Healing Analyzer, ETL Checker, Vulnerability Analyzer |
| **High** | Architect/DBA approval | Schema Validator (production data access) |

### 15.5 Reference Documents

- **Full PRD:** `docs/planning/prd-agent-skills-integration.md` — 28 FRs, 20 stories, cost-benefit analysis
- **Architecture Board Approval:** `docs/reports/architecture-board-review-agent-skills-20260215.md` — Score: 7.8/10, APPROVED with 5 conditions
- **Executive Strategy:** `docs/evaluations/anthropic-agent-skills-executive-strategy.md` — ROI: 1.5x (3-year), payback: 18-24 months
- **Technical Review:** `docs/evaluations/anthropic-agent-skills-technical-review.md` — Feasibility: High

---

## 16. Agent Extensibility & Custom Agents (Post-MVP — Epic 6 Phase 3)

### 16.1 Overview

QUALISYS supports admin-configured custom agents per client request through a runtime Agent Registry Service. This capability transforms the platform from "a product with agents" to "a platform for agents" without requiring code deployment for new agent additions.

**Target Personas:**
- **Platform Admin** (QUALISYS internal): Register agents, manage global definitions, version prompts, monitor circuit breakers
- **Tenant Admin** (Client organization): Enable/disable agents, customize prompts, override LLM provider

### 16.2 Custom Agent Capabilities

| Capability | Description | Stories |
|-----------|-------------|---------|
| **Agent Registry** | Runtime registration, discovery, lifecycle management | Story 6.9 |
| **Per-Tenant Customization** | Client-specific prompts (append/prepend/replace), enable/disable, LLM override | Story 6.10 |
| **Fault Isolation** | Per-agent token budgets, hard timeouts, circuit breakers | Story 6.11 |
| **Prompt Versioning** | Semantic versioning, gradual rollout (% tenant bucketing), rollback | Story 6.12 |

### 16.3 RBAC for Custom Agents

Custom agents inherit the existing 6-role RBAC matrix. Tenant admins can configure which roles have access to custom agents within their organization. All custom agent executions are audit-logged with tenant_id, agent_id, and actor identity.

### 16.4 Reference Documents

- **Tech Spec:** `docs/planning/tech-spec-agent-extensibility-framework.md` — Architecture, API contracts, database schema
- **Epic Stories:** Stories 6.9-6.12 in `docs/epics/epics.md`

---

## Document References

| Document | Path | Relevance |
|----------|------|-----------|
| PRD (FR32-FR37) | `docs/planning/prd.md` | Agent functional requirements |
| Architecture | `docs/architecture/architecture.md` | Technical agent design |
| Epics | `docs/epics/epics.md` | Epic 2 (MVP agents), Epic 6 (Post-MVP + Custom Agents), Epic 7 (Agent Skills) |
| UX Design | `docs/planning/ux-design-specification.md` | Agent UI/UX |
| BA+QA Research | `docs/improvements/research_document-2026-02-03.md` | BAConsultant + QAConsultant design |
| BA+QA Improvement Plan | `docs/improvements/improvement_plan-2026-02-03.md` | Implementation roadmap |
| AutomationConsultant Research | `docs/improvements/automation_consultant_ai_agent_docs/research_automationConsultantAIAgent-2026-02-06.md` | AutomationConsultant design |
| Sprint Change Proposal | `docs/sprint-change-proposal-2026-02-06.md` | Agent restructuring (8→6) |
| Agent Skills PRD | `docs/planning/prd-agent-skills-integration.md` | 21 skills, progressive disclosure model |
| Agent Extensibility Tech Spec | `docs/planning/tech-spec-agent-extensibility-framework.md` | Runtime registry, per-tenant customization |
| Agent Skills Evaluations | `docs/evaluations/anthropic-agent-skills-*.md` | Architecture board, executive strategy, technical review |

---

**Document Version:** 2.0
**Last Updated:** 2026-02-15
**Compiled By:** PM Agent (John) — BMad Method v6
**Change Log:** v2.0 — Added Section 15 (Agent Skills Integration) and Section 16 (Agent Extensibility & Custom Agents). Updated document references. v1.0 — Original 7-agent specification.
