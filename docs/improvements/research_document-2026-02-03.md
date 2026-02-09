# Qualisys – Research Document 2026-02-03

## 1. Vision & Problem Statement
Modern software systems increasingly rely on AI and non-deterministic components. Traditional QA and testing approaches fail to adequately validate AI behavior, data drift, bias, and explainability. Qualisys introduces a new category: **AI System Quality Assurance**, combining intelligent document ingestion, codebase understanding, and multi-agent AI collaboration with strict human-in-the-loop governance.

## 2. Core Principles
- Human-in-the-loop at every critical stage
- Clear separation of responsibilities between agents
- Domain-agnostic by design
- Governance-first, automation-second
- Manual-testing-friendly

## 3. Current Agent Landscape
As of now, Qualisys includes two AI agents:
1. BusinessAnalyst AI Agent
2. QAConsultant AI Agent

Automation is intentionally excluded at this stage.

## 4. Business Analyst AI Agent (BA AI)

### 4.1 Mission
Transform unstructured and structured client inputs into **client-approved, high-quality, test-ready user stories**.

### 4.2 Inputs
- RFI, RFP, SRS, FRS
- JIRA, Confluence
- PDF, Word, Excel, CSV
- JSON, Markdown
- Meeting notes, emails
- Git repositories (read-only)

### 4.3 Responsibilities
- Requirements extraction and analysis
- Functional & non-functional requirement identification
- Gap, ambiguity, and assumption detection
- Domain adaptation (finance, healthcare, e-commerce, etc.)
- User story creation with acceptance criteria
- Edge case and negative scenario identification
- AI-specific requirement identification (bias, drift, explainability)
- Requirement traceability
- Internal and client review support
- Final packaging of approved user stories

### 4.4 User Story Structure
- Title
- Persona / Actor
- Business intent
- User story statement
- Functional flow
- Acceptance criteria
- Edge & negative scenarios
- Non-functional requirements
- Dependencies
- AI-specific notes
- Traceability references

### 4.5 User Story Quality Scoring
Each story is scored across:
- Clarity
- Completeness
- Business value
- Testability
- Acceptance criteria quality
- Edge/negative coverage
- Non-functional coverage
- Traceability

Max score: 40 | Minimum pass: 32

Dual-review approval required before handoff:
1. **Internal Team Review** — BA/QA/PM reviews story for quality, completeness, and technical accuracy
2. **Client Review** — Client stakeholder reviews for business intent and acceptance criteria correctness

Only stories approved by BOTH internal team AND client are released to QAConsultant.

---

## 5. QAConsultant AI Agent

### 5.1 Mission
Ensure **quality validation, manual testing governance, and sprint readiness** based on approved user stories.

### 5.2 Dual Role Model
- Test Consultant
- ScrumMaster

---

## 6. Test Consultant Role

### Responsibilities
- Test strategy creation
- Test plan documentation
- Manual black-box test case generation
- Boundary value & equivalence analysis
- AI behavior validation
- Test coverage assurance
- Requirement–test traceability matrix
- Manual execution support

### Supported Testing Types
- Smoke Testing
- Sanity Testing
- Integration Testing
- Regression Testing
- Usability Testing
- Acceptance Testing (UAT)

### Checklist-Driven Testing
For each testing type, AI generates structured execution checklists including:
- Scenario
- Preconditions
- Expected result
- Pass/Fail
- Notes / defect reference
- Priority

### Test Data Generation
- Synthetic, masked, realistic test data
- Linked directly to checklist items
- Domain-aware

Human QA approval required before execution.

---

## 7. ScrumMaster Role

### Responsibilities
- Sprint readiness validation
- JIRA & Azure DevOps data preparation
- MCP server coordination
- AI bot schema alignment
- Sprint lifecycle support

Human approval required before sprint start.

---

## 8. Governance & Human-in-the-Loop

### Artifact Status Lifecycle (Standard)
Draft → Ready for Review → Review Done → Approved → Released

### User Story Lifecycle (Dual-Review)
Draft → Ready for Review → Internal Review Done → Client Review → Client Approved → Released

User stories specifically require TWO sequential mandatory reviews:
1. **Internal Team Review** — Internal BA/QA/PM reviews for quality and completeness
2. **Client Review** — Client stakeholder validates business intent and acceptance criteria

Only after both reviews are complete does the story become available to downstream agents.

No AI agent can self-approve.

---

## 9. Responsibility Ownership (Current State)

### Owned by BA AI
- Requirements
- User stories
- Quality scoring
- Traceability

### Owned by QAConsultant AI
- Test strategy & plan
- Manual test cases
- Checklists
- Sprint readiness

### Platform-Level (Not Agent-Owned)
- Quality gate orchestration
- Artifact status model (DB/UI)
- Approval enforcement
- Prompt guardrails

---

## 10. Current Scope Boundary
- No automation scripting
- No unit testing
- No CI/CD ownership

These will be addressed by AutomationConsultant AI Agent in next phase.

