---
name: bmad-agent-enhancer
description: Enhance BMAD Method agents with project-aware intelligence for QUALISYS development. Automatically routes tasks to the correct BMAD agent, injects sprint and project state from sprint-status.yaml and bmm-workflow-status.yaml, provides codebase structure awareness, and guides cross-agent handoffs. Use when activating any BMAD agent, starting a workflow, checking project status, or when the user mentions agent names (Amelia, Bob, John, Winston, Mary, Murat, Sally, Paige) or BMAD commands (*develop-story, *create-story, *code-review, *sprint-planning, *create-architecture, *prd, *tech-spec, *framework, *automate, *test-design, *document-project, *workflow-status, *party-mode).
---

# BMAD Agent Enhancer for QUALISYS

This skill augments the 8 BMAD agents with live project awareness, codebase intelligence, and cross-agent handoff guidance. It does **not** replace agent personas or override their rules — it provides the context layer they need to operate at peak effectiveness.

## Context Pre-loading Protocol

Before any BMAD agent begins work, gather and present this context:

### Always Load First

1. `.bmad/bmm/config.yaml` — extract `{user_name}`, `{communication_language}`, `{output_folder}`
2. `docs/sprint-status.yaml` — extract `current_epic`, `current_sprint`, next `ready-for-dev` story, `blocking_items`
3. `docs/bmm-workflow-status.yaml` — extract current phase, `selected_track`

Present a brief status summary to the agent:
- Current phase and track
- Active epic and sprint
- Next actionable story (first `ready-for-dev` or first `backlog` in active epic)
- Any blocking items

### Agent-Specific Context

**DEV Agent (Amelia) — before `*develop-story` or `*code-review`:**
- Load the story file: `docs/stories/{epic-id}/{story-id}.md`
- Load the story context XML: `docs/stories/{epic-id}/{story-id}.context.xml`
- Load the epic tech-spec if it exists: `docs/stories/{epic-id}/tech-spec-{epic-id}.md`
- Verify story status is `ready-for-dev` or `in-progress` before proceeding
- If story is not approved, halt and suggest running SM `*story-ready-for-dev` first

**SM Agent (Bob) — before `*create-story` or `*create-story-context`:**
- Load `docs/epics.md` for epic definitions
- List the epic subdirectory for the current epic to see existing stories
- Check sprint-status.yaml for the next undrafted story in the active epic

**TEA Agent (Murat) — before any test workflow:**
- Load `.bmad/bmm/testarch/tea-index.csv` for knowledge fragment selection
- Scan `backend/tests/` for existing test files relevant to the story or epic

**Architect (Winston) — before `*create-architecture` or `*implementation-readiness`:**
- Load `docs/prd.md` for requirements context
- Load `docs/ux-design-specification.md` if it exists
- Scan `backend/src/patterns/` for established integration patterns

**PM (John) — before `*create-prd` or `*create-epics-and-stories`:**
- Load `docs/product-brief-QUALISYS-2025-12-01.md` if it exists
- Load existing PRD and architecture for epics/stories workflow

## Agent Routing

When the user's intent is ambiguous, use this routing table to identify the correct agent:

| User says something like... | Route to | Load agent file |
|-----------------------------|----------|----------------|
| "draft the next story" / "prepare story 2-10" | SM (Bob) | `.bmad/bmm/agents/sm.md` |
| "implement story" / "start coding" / "dev story" | DEV (Amelia) | `.bmad/bmm/agents/dev.md` |
| "review the code" / "code review" | DEV (Amelia) | `.bmad/bmm/agents/dev.md` |
| "create the PRD" / "write requirements" | PM (John) | `.bmad/bmm/agents/pm.md` |
| "design the architecture" / "system design" | Architect (Winston) | `.bmad/bmm/agents/architect.md` |
| "brainstorm" / "research" / "product brief" | Analyst (Mary) | `.bmad/bmm/agents/analyst.md` |
| "test strategy" / "test automation" / "CI pipeline" | TEA (Murat) | `.bmad/bmm/agents/tea.md` |
| "write docs" / "API documentation" / "README" | Tech Writer (Paige) | `.bmad/bmm/agents/tech-writer.md` |
| "UX design" / "wireframes" / "user flows" | UX Designer (Sally) | `.bmad/bmm/agents/ux-designer.md` |
| "what's next?" / "project status" | Any agent → `*workflow-status` | Current or suggest appropriate |
| "sprint planning" / "update sprint" | SM (Bob) | `.bmad/bmm/agents/sm.md` |
| "mark story done" | SM (Bob) | `.bmad/bmm/agents/sm.md` |

## Cross-Agent Handoff Guide

When an agent completes a workflow, recommend the next step:

| Just completed | Next step | Switch to |
|----------------|-----------|-----------|
| SM: story drafted | Generate story context XML | SM: `*create-story-context` |
| SM: story context generated | Mark ready for dev | SM: `*story-ready-for-dev` |
| SM: story marked ready | **Open fresh chat** → implement | DEV: `*develop-story` |
| DEV: story implemented | **Open fresh chat** → review | DEV: `*code-review` |
| DEV: code review approved | Mark story done | SM: `*story-done` |
| SM: all epic stories done | Epic retrospective | SM: `*epic-retrospective` |
| Analyst: product brief done | Create PRD | PM: `*create-prd` |
| PM: PRD done | Create UX design OR architecture | Sally or Winston |
| Architect: architecture done | Create epics and stories | PM: `*create-epics-and-stories` |
| PM: epics created | Validate readiness | Architect: `*implementation-readiness` |
| Architect: readiness approved | Sprint planning | SM: `*sprint-planning` |

**CRITICAL:** Always recommend a **fresh chat** when switching agents. This prevents context pollution and is a core BMad Method principle.

## QUALISYS Codebase Quick Reference

For full details, see [.bmad/skills/bmad-agent-enhancer/project-context.md](../../.bmad/skills/bmad-agent-enhancer/project-context.md).

Key paths for code-aware agents (DEV, TEA):
- **API routes:** `backend/src/api/v1/{domain}/router.py`
- **Services:** `backend/src/services/{name}.py`
- **AI Agents:** `backend/src/services/agents/{agent}.py`
- **Patterns:** `backend/src/patterns/{name}_pattern.py` — llm, pgvector, sse, playwright
- **Tests:** `backend/tests/{unit,integration,security}/`
- **Migrations:** `backend/alembic/versions/{NNN}_{desc}.py`
- **Stories:** `docs/stories/{epic-id}/{story-id}.md`
- **Story context:** `docs/stories/{epic-id}/{story-id}.context.xml`

## Error Recovery

| Problem | Resolution |
|---------|-----------|
| Agent says "config not loaded" | Read `.bmad/bmm/config.yaml` and supply values: user_name=Azfar, communication_language=English, output_folder=docs |
| Story file not found | Check `docs/sprint-status.yaml` for the correct story ID and path format |
| DEV refuses to start — story not approved | Run SM `*story-ready-for-dev` or `*create-story-context` first |
| Missing `.context.xml` for story | Run SM `*create-story-context` workflow to generate it |
| Sprint status seems stale | Remind user to update `docs/sprint-status.yaml` after completing stories |
| Agent persona not active | Load the agent file first via `.bmad/bmm/agents/{id}.md`, then re-run the command |

## Additional Resources

- For complete agent details, menus, and handoff rules: [agent-registry.md](../../.bmad/skills/bmad-agent-enhancer/agent-registry.md)
- For QUALISYS tech stack, patterns, and conventions: [project-context.md](../../.bmad/skills/bmad-agent-enhancer/project-context.md)
