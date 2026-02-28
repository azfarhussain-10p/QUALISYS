---
name: bmad-agent-enhancer
description: Enhance BMAD Method agents with project-aware intelligence for QUALISYS development. Automatically routes tasks to the correct BMAD agent, injects sprint and project state, provides codebase structure awareness, and guides cross-agent handoffs. Use when activating any BMAD agent, starting a workflow, checking project status, or when the user mentions agent names (Amelia, Bob, John, Winston, Mary, Murat, Sally, Paige) or BMAD commands (*develop-story, *create-story, *code-review, *sprint-planning, *create-architecture, *prd, *tech-spec, *framework, *automate, *test-design, *document-project, *workflow-status, *party-mode).
allowed-tools: Read, Grep, Glob, Bash(cat *), Bash(ls *), Bash(head *), Bash(python *)
---

# BMAD Agent Enhancer for QUALISYS

This skill augments the 8 BMAD agents with live project awareness, codebase intelligence, and cross-agent handoff guidance. It does **not** replace agent personas or override their rules — it provides the context layer they need to operate at peak effectiveness.

## Live Project State

The following sections inject live data every time this skill loads. Claude Code replaces the `!`command`` blocks with actual output.

### Sprint Status (live)

!`head -60 docs/sprint-status.yaml`

### Workflow Phase (live)

!`cat docs/bmm-workflow-status.yaml`

### BMM Configuration (live)

!`cat .bmad/bmm/config.yaml`

## Argument-Based Agent Routing

When invoked as `/bmad-agent-enhancer $ARGUMENTS`, route based on the first argument:

| Argument | Action |
|----------|--------|
| `sm` or `bob` | Load SM agent → `.bmad/bmm/agents/sm.md` |
| `dev` or `amelia` | Load DEV agent → `.bmad/bmm/agents/dev.md` |
| `pm` or `john` | Load PM agent → `.bmad/bmm/agents/pm.md` |
| `architect` or `winston` | Load Architect → `.bmad/bmm/agents/architect.md` |
| `analyst` or `mary` | Load Analyst → `.bmad/bmm/agents/analyst.md` |
| `tea` or `murat` | Load TEA → `.bmad/bmm/agents/tea.md` |
| `ux` or `sally` | Load UX Designer → `.bmad/bmm/agents/ux-designer.md` |
| `writer` or `paige` | Load Tech Writer → `.bmad/bmm/agents/tech-writer.md` |
| `status` | Read sprint-status.yaml and recommend next action |
| (no argument) | Auto-detect from conversation context |

After routing, follow the agent's own activation sequence. This skill supplements — never overrides — the agent's persona, menu, and rules.

## Context Pre-loading Protocol

Before any BMAD agent begins work, supply this context:

### Always Load First

1. `.bmad/bmm/config.yaml` — `{user_name}`, `{communication_language}`, `{output_folder}`
2. `docs/sprint-status.yaml` — `current_epic`, `current_sprint`, next `ready-for-dev` story
3. `docs/bmm-workflow-status.yaml` — current phase, `selected_track`

### Agent-Specific Context

**DEV Agent (Amelia) — before `*develop-story` or `*code-review`:**
- Load story: `docs/stories/{epic-id}/{story-id}.md`
- Load context XML: `docs/stories/{epic-id}/{story-id}.context.xml`
- Load epic tech-spec if exists: `docs/stories/{epic-id}/tech-spec-{epic-id}.md`
- Verify story status is `ready-for-dev` or `in-progress`

**SM Agent (Bob) — before `*create-story`:**
- Load `docs/epics.md` for epic definitions
- List epic subdirectory for current epic
- Check sprint-status.yaml for next undrafted story

**TEA Agent (Murat) — before any test workflow:**
- Load `.bmad/bmm/testarch/tea-index.csv` for knowledge fragments
- Scan `backend/tests/` for related test files

**Architect (Winston) — before `*create-architecture`:**
- Load `docs/prd.md` and `docs/ux-design-specification.md`
- Scan `backend/src/patterns/` for established patterns

**PM (John) — before `*create-prd` or `*create-epics-and-stories`:**
- Load product brief and existing PRD if available

## Intent → Agent Routing Table

| User says... | Route to | Load agent file |
|-------------|----------|----------------|
| "draft the next story" | SM (Bob) | `.bmad/bmm/agents/sm.md` |
| "implement story" / "dev story" | DEV (Amelia) | `.bmad/bmm/agents/dev.md` |
| "review the code" | DEV (Amelia) | `.bmad/bmm/agents/dev.md` |
| "create PRD" / "requirements" | PM (John) | `.bmad/bmm/agents/pm.md` |
| "architecture" / "system design" | Architect (Winston) | `.bmad/bmm/agents/architect.md` |
| "brainstorm" / "research" | Analyst (Mary) | `.bmad/bmm/agents/analyst.md` |
| "test strategy" / "automation" | TEA (Murat) | `.bmad/bmm/agents/tea.md` |
| "write docs" / "API docs" | Tech Writer (Paige) | `.bmad/bmm/agents/tech-writer.md` |
| "UX design" / "wireframes" | UX Designer (Sally) | `.bmad/bmm/agents/ux-designer.md` |
| "what's next?" / "status" | Any → `*workflow-status` | Current or suggest |
| "sprint planning" | SM (Bob) | `.bmad/bmm/agents/sm.md` |

## Cross-Agent Handoff Guide

When an agent completes a workflow, recommend the next step:

| Just completed | Next step | Switch to |
|----------------|-----------|-----------|
| SM: story drafted | Generate story context XML | SM: `*create-story-context` |
| SM: story context generated | Mark ready for dev | SM: `*story-ready-for-dev` |
| SM: story marked ready | **Fresh chat** → implement | DEV: `*develop-story` |
| DEV: story implemented | **Fresh chat** → review | DEV: `*code-review` |
| DEV: review approved | Mark story done | SM: `*story-done` |
| SM: all epic stories done | Retrospective | SM: `*epic-retrospective` |
| Analyst: brief done | Create PRD | PM: `*create-prd` |
| PM: PRD done | UX design or architecture | Sally or Winston |
| Architect: architecture done | Create epics | PM: `*create-epics-and-stories` |
| PM: epics created | Validate readiness | Architect: `*implementation-readiness` |
| Architect: readiness approved | Sprint planning | SM: `*sprint-planning` |

**CRITICAL:** Always recommend a **fresh chat** when switching agents.

## QUALISYS Codebase Quick Reference

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
| "config not loaded" | Read `.bmad/bmm/config.yaml`: user_name=Azfar, communication_language=English, output_folder=docs |
| Story file not found | Check `docs/sprint-status.yaml` for correct story ID |
| DEV refuses — story not approved | Run SM `*story-ready-for-dev` first |
| Missing `.context.xml` | Run SM `*create-story-context` |
| Sprint status stale | Update `docs/sprint-status.yaml` after story completion |
| Agent persona not active | Load agent file first, then re-run command |

## Additional Resources

- Agent registry (all menus, handoffs): [.bmad/skills/bmad-agent-enhancer/agent-registry.md](.bmad/skills/bmad-agent-enhancer/agent-registry.md)
- Project context (tech stack, patterns): [.bmad/skills/bmad-agent-enhancer/project-context.md](.bmad/skills/bmad-agent-enhancer/project-context.md)
