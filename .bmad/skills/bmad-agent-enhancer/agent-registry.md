# BMAD Agent Registry — QUALISYS

Quick reference for all BMAD agents, their capabilities, menu commands, and routing rules.

## Agent Index

| ID | Name | Icon | Role | Phase |
|----|------|------|------|-------|
| analyst | Mary | 📊 | Strategic Business Analyst | 1 — Analysis |
| pm | John | 📋 | Product Manager | 2 — Planning, 3 — Solutioning |
| ux-designer | Sally | 🎨 | UX Designer | 2 — Planning |
| architect | Winston | 🏗️ | System Architect | 3 — Solutioning |
| sm | Bob | 🏃 | Scrum Master | 4 — Implementation |
| dev | Amelia | 💻 | Developer Agent | 4 — Implementation |
| tea | Murat | 🧪 | Master Test Architect | Cross-phase |
| tech-writer | Paige | 📚 | Technical Writer | Cross-phase |

## Agent Details

### Analyst — Mary 📊

- **File:** `.bmad/bmm/agents/analyst.md`
- **Identity:** Senior analyst specialising in market research, competitive analysis, and requirements elicitation.
- **Menu commands:**
  - `*workflow-init` — Start a new sequenced workflow path
  - `*workflow-status` — Check workflow status
  - `*brainstorm-project` — Guided brainstorming
  - `*research` — Guided research
  - `*product-brief` — Create a project brief
  - `*document-project` — Generate comprehensive documentation of existing project
  - `*party-mode` — Multi-agent collaboration

### Product Manager — John 📋

- **File:** `.bmad/bmm/agents/pm.md`
- **Identity:** Product management veteran, expert in market research and user behavior insights.
- **Menu commands:**
  - `*workflow-init` — Start a new sequenced workflow path
  - `*workflow-status` — Check workflow status
  - `*create-prd` — Create Product Requirements Document
  - `*create-epics-and-stories` — Break PRD into epics and stories
  - `*validate-prd` — Validate PRD completeness and quality
  - `*tech-spec` — Create Tech Spec (simple work efforts)
  - `*validate-tech-spec` — Validate Technical Specification
  - `*correct-course` — Course correction analysis
  - `*create-excalidraw-flowchart` — Create process flow diagram
  - `*party-mode` — Multi-agent collaboration

### UX Designer — Sally 🎨

- **File:** `.bmad/bmm/agents/ux-designer.md`
- **Identity:** Senior UX Designer, expert in user research, interaction design, AI-assisted tools.
- **Menu commands:**
  - `*workflow-status` — Check workflow status
  - `*create-ux-design` — Conduct Design Thinking Workshop
  - `*validate-design` — Validate UX Specification
  - `*create-excalidraw-wireframe` — Create wireframe (Excalidraw)
  - `*party-mode` — Multi-agent collaboration

### Architect — Winston 🏗️

- **File:** `.bmad/bmm/agents/architect.md`
- **Identity:** Senior architect, distributed systems, cloud infrastructure, API design.
- **Menu commands:**
  - `*workflow-status` — Check workflow status
  - `*create-architecture` — Produce Scale Adaptive Architecture
  - `*validate-architecture` — Validate Architecture Document
  - `*implementation-readiness` — Validate PRD/UX/Architecture/Epics alignment
  - `*create-excalidraw-diagram` — Create system architecture diagram
  - `*create-excalidraw-dataflow` — Create data flow diagram
  - `*party-mode` — Multi-agent collaboration

### Scrum Master — Bob 🏃

- **File:** `.bmad/bmm/agents/sm.md`
- **Identity:** Certified Scrum Master with deep technical background. Story preparation specialist.
- **Menu commands:**
  - `*workflow-status` — Check workflow status
  - `*sprint-planning` — Generate/update sprint-status.yaml
  - `*create-epic-tech-context` — Create Epic Tech Spec
  - `*validate-epic-tech-context` — Validate Epic Tech Spec
  - `*create-story` — Create a Draft Story
  - `*validate-create-story` — Validate Story Draft
  - `*create-story-context` — Assemble Story Context XML and mark ready
  - `*validate-create-story-context` — Validate Story Context XML
  - `*story-ready-for-dev` — Mark story ready without generating context
  - `*epic-retrospective` — Facilitate team retrospective
  - `*correct-course` — Course correction
  - `*party-mode` — Multi-agent collaboration

### Developer — Amelia 💻

- **File:** `.bmad/bmm/agents/dev.md`
- **Identity:** Senior Software Engineer. Strict adherence to acceptance criteria and Story Context XML.
- **Activation rule:** Will NOT start implementation until a story is loaded and Status == Approved.
- **Menu commands:**
  - `*workflow-status` — Check workflow status
  - `*develop-story` — Execute Dev Story workflow (implement tasks + tests)
  - `*story-done` — Mark story done after DoD complete
  - `*code-review` — Thorough QA code review on story flagged Ready for Review
- **Special behaviors:**
  - Reads entire story markdown and treats it as CRITICAL
  - Loads Story Context XML from "Dev Agent Record → Context Reference"
  - Executes continuously without pausing for milestones — halts only for blockers or completion

### Test Architect — Murat 🧪

- **File:** `.bmad/bmm/agents/tea.md`
- **Identity:** Test architect specializing in CI/CD, automated frameworks, quality gates.
- **Startup:** Consults `tea-index.csv` to select knowledge fragments before recommendations.
- **Menu commands:**
  - `*workflow-status` — Check workflow status
  - `*framework` — Initialize test framework architecture
  - `*atdd` — Generate E2E tests before implementation
  - `*automate` — Generate comprehensive test automation
  - `*test-design` — Create comprehensive test scenarios
  - `*trace` — Map requirements to tests + quality gate decision
  - `*nfr-assess` — Validate non-functional requirements
  - `*ci` — Scaffold CI/CD quality pipeline
  - `*test-review` — Review test quality
  - `*party-mode` — Multi-agent collaboration

### Technical Writer — Paige 📚

- **File:** `.bmad/bmm/agents/tech-writer.md`
- **Identity:** Expert in CommonMark, DITA, OpenAPI. Transforms complex concepts into accessible documentation.
- **Startup:** Loads documentation-standards.md into permanent memory.
- **Menu commands:**
  - `*document-project` — Comprehensive project documentation
  - `*create-api-docs` — API documentation (OpenAPI/Swagger)
  - `*create-architecture-docs` — Architecture documentation with diagrams
  - `*create-user-guide` — User-facing guides and tutorials
  - `*audit-docs` — Documentation quality review
  - `*generate-mermaid` — Generate Mermaid diagrams
  - `*create-excalidraw-flowchart` — Excalidraw flowchart
  - `*create-excalidraw-diagram` — Excalidraw system architecture diagram
  - `*create-excalidraw-dataflow` — Excalidraw data flow diagram
  - `*validate-doc` — Validate against CommonMark standards
  - `*improve-readme` — Review and improve README
  - `*explain-concept` — Technical explanation with examples
  - `*standards-guide` — Show documentation standards reference
  - `*party-mode` — Multi-agent collaboration

## Intent → Agent Routing

| User intent | Agent | Trigger command |
|-------------|-------|-----------------|
| "What should I do next?" | Any → `*workflow-status` | `*workflow-status` |
| Brainstorm, research, brief | Analyst (Mary) | `*brainstorm-project`, `*research`, `*product-brief` |
| PRD, requirements, epics | PM (John) | `*create-prd`, `*create-epics-and-stories` |
| UX design, wireframes | UX Designer (Sally) | `*create-ux-design`, `*create-excalidraw-wireframe` |
| Architecture, readiness | Architect (Winston) | `*create-architecture`, `*implementation-readiness` |
| Sprint planning, story lifecycle | SM (Bob) | `*sprint-planning`, `*create-story`, `*story-ready-for-dev` |
| Implement code, develop story | DEV (Amelia) | `*develop-story` |
| Code review | DEV (Amelia) | `*code-review` |
| Test strategy, automation | TEA (Murat) | `*framework`, `*automate`, `*test-design` |
| Documentation | Tech Writer (Paige) | `*document-project`, `*create-api-docs` |
| Course correction | PM (John) or SM (Bob) | `*correct-course` |
| Multi-agent discussion | Any → `*party-mode` | `*party-mode` |

## Cross-Agent Handoff Matrix

| Completed workflow | Next agent | Next action |
|--------------------|------------|-------------|
| Analyst: `*product-brief` | PM (John) | `*create-prd` |
| PM: `*create-prd` | UX Designer (Sally) | `*create-ux-design` |
| PM: `*create-prd` | Architect (Winston) | `*create-architecture` |
| UX Designer: `*create-ux-design` | Architect (Winston) | `*create-architecture` |
| Architect: `*create-architecture` | PM (John) | `*create-epics-and-stories` |
| PM: `*create-epics-and-stories` | Architect (Winston) | `*implementation-readiness` |
| Architect: `*implementation-readiness` | SM (Bob) | `*sprint-planning` |
| SM: `*sprint-planning` | SM (Bob) | `*create-epic-tech-context` |
| SM: `*create-epic-tech-context` | SM (Bob) | `*create-story` |
| SM: `*create-story` | SM (Bob) | `*create-story-context` |
| SM: `*create-story-context` | SM (Bob) | `*story-ready-for-dev` |
| SM: `*story-ready-for-dev` | DEV (Amelia) | `*develop-story` |
| DEV: `*develop-story` | DEV (Amelia) | `*code-review` (fresh chat) |
| DEV: `*code-review` approved | SM (Bob) | `*story-done` |
| SM: all stories done in epic | SM (Bob) | `*epic-retrospective` |
