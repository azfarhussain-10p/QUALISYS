# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a **BMad Method v6** project - an AI-driven agile development framework that uses specialized AI agents and workflows to guide software development from conception to implementation.

The repository contains:
- **BMad Method Module (BMM)** - Core orchestration system with 12 specialized AI agents for agile development
- **BMad Builder Module (BMB)** - Tools for creating and extending BMad components
- **BMad Core** - Foundation framework with shared utilities and base workflows

## Key Architecture

### Multi-Module System

The codebase is organized into three primary modules under `.bmad/`:

1. **`.bmad/bmm/`** - BMad Method Module
   - 12 specialized agents (PM, Architect, SM, DEV, TEA, Analyst, UX-Designer, Tech-Writer, etc.)
   - 34+ workflows across 4 development phases
   - Story-centric implementation with lifecycle tracking
   - Scale-adaptive system (Quick Flow, BMad Method, Enterprise Method tracks)

2. **`.bmad/bmb/`** - BMad Builder Module
   - Creation workflows for agents, workflows, and complete modules
   - Editing and maintenance workflows
   - Audit and quality validation tools
   - Legacy conversion utilities

3. **`.bmad/core/`** - Core Framework
   - BMad Master orchestration agent
   - Shared utilities (brainstorming, party-mode)
   - Common tasks and tools
   - Base framework components

### Agent System

Agents are AI personas with specialized expertise, delivered as markdown files. Each agent:
- Has source YAML in module directories (`.bmad/{module}/agents/*.yaml`)
- Compiles to markdown for IDE consumption (`.claude/commands/bmad/{module}/agents/*.md`)
- Includes command structure with fuzzy matching
- Integrates with specific workflows

### Workflow Architecture

Workflows are structured multi-step processes that guide users through complex tasks:
- Configuration: `workflow.yaml` (defines metadata, variables, web bundles)
- Instructions: `instructions.md` (agent execution prompts)
- Templates: `template.md` (output document structures)
- Web bundles: optional external resources fetched during execution

Workflows exist in source form (`.bmad/{module}/workflows/`) and compile to slash commands (`.claude/commands/`).

### Project Tracking

Two critical YAML files track project state:

1. **`docs/bmm-workflow-status.yaml`** - Overall project workflow tracking
   - Created by `workflow-init`
   - Tracks phase progression (Analysis → Planning → Solutioning → Implementation)
   - Determines which track (Quick Flow, BMad Method, Enterprise Method)
   - Used by agents to provide context-aware guidance

2. **`docs/sprint-status.yaml`** - Implementation phase tracking
   - Created by `sprint-planning` workflow
   - Tracks all epics and stories with statuses
   - Critical for SM and DEV agents during Phase 4
   - Story lifecycle: backlog → drafted → ready → in-progress → review → done

## Common Workflows and Commands

### Initialization and Status

```bash
# Initialize a new BMad project (run via Analyst agent)
/bmad:bmm:workflows:workflow-init

# Check current project status and next steps (run via any agent)
/bmad:bmm:workflows:workflow-status
```

### Phase 1: Analysis (Optional)

```bash
# Brainstorm project ideas (Analyst)
/bmad:bmm:workflows:brainstorm-project

# Research domain, market, or technical topics (Analyst)
/bmad:bmm:workflows:research

# Create product brief (Analyst)
/bmad:bmm:workflows:product-brief
```

### Phase 2: Planning (Required)

```bash
# Create Product Requirements Document - BMad/Enterprise tracks (PM)
/bmad:bmm:workflows:prd

# Create technical specification - Quick Flow track (PM)
/bmad:bmm:workflows:tech-spec

# Create UX design artifacts (UX-Designer)
/bmad:bmm:workflows:create-ux-design
```

### Phase 3: Solutioning (Track-dependent)

```bash
# Create architecture document - BMad/Enterprise tracks (Architect)
/bmad:bmm:workflows:architecture

# Create epics and stories from PRD + Architecture (PM)
/bmad:bmm:workflows:create-epics-and-stories

# Validate all planning documents are aligned (Architect)
/bmad:bmm:workflows:implementation-readiness
```

### Phase 4: Implementation (Required)

```bash
# Initialize sprint tracking (SM)
/bmad:bmm:workflows:sprint-planning

# Create epic technical context (SM)
/bmad:bmm:workflows:epic-tech-context

# Draft next story (SM)
/bmad:bmm:workflows:create-story

# Add story implementation context (SM)
/bmad:bmm:workflows:story-context

# Mark story as ready for development (SM)
/bmad:bmm:workflows:story-ready

# Implement story (DEV)
/bmad:bmm:workflows:dev-story

# Review completed story (DEV)
/bmad:bmm:workflows:code-review

# Mark story as done (SM)
/bmad:bmm:workflows:story-done

# Epic retrospective (SM)
/bmad:bmm:workflows:retrospective

# Handle scope changes mid-sprint (SM)
/bmad:bmm:workflows:correct-course
```

### Building Custom BMad Components

```bash
# Create new agent (BMad Builder)
/bmad:bmb:workflows:create-agent

# Create new workflow (BMad Builder)
/bmad:bmb:workflows:create-workflow

# Create complete module (BMad Builder)
/bmad:bmb:workflows:create-module

# Strategic module planning (BMad Builder)
/bmad:bmb:workflows:module-brief

# Edit existing agent (BMad Builder)
/bmad:bmb:workflows:edit-agent

# Edit existing workflow (BMad Builder)
/bmad:bmb:workflows:edit-workflow

# Audit workflow quality (BMad Builder)
/bmad:bmb:workflows:audit-workflow

# Convert legacy v4 components (BMad Builder)
/bmad:bmb:workflows:convert-legacy
```

### Multi-Agent Collaboration

```bash
# Engage all agents in group discussion
/bmad:core:workflows:party-mode

# Interactive brainstorming with creative techniques
/bmad:core:workflows:brainstorming
```

## Agent Reference Guide

When working with this codebase, reference the appropriate agent based on the task:

- **Analyst** (`/bmad:bmm:agents:analyst`) - Project initialization, brainstorming, research, product briefs
- **PM** (`/bmad:bmm:agents:pm`) - Requirements (PRD/tech-spec), epics and stories creation
- **UX-Designer** (`/bmad:bmm:agents:ux-designer`) - UX design, wireframes, visual artifacts
- **Architect** (`/bmad:bmm:agents:architect`) - Architecture decisions, technical design, implementation readiness
- **SM** (`/bmad:bmm:agents:sm`) - Sprint management, story lifecycle, epic context
- **DEV** (`/bmad:bmm:agents:dev`) - Story implementation, code reviews
- **TEA** (`/bmad:bmm:agents:tea`) - Test architecture and quality assurance
- **Tech-Writer** (`/bmad:bmm:agents:tech-writer`) - Documentation creation and maintenance
- **BMad Builder** (`/bmad:bmb:agents:bmad-builder`) - Creating/editing agents, workflows, modules
- **BMad Master** (`/bmad:core:agents:bmad-master`) - Overall orchestration and coordination

## Scale Adaptive System

BMad Method automatically adapts to project complexity through three tracks:

### Quick Flow Track
- **Planning**: tech-spec only
- **Time**: Hours to 1 day
- **Use for**: Bug fixes, simple features, clear scope
- **Workflows**: workflow-init → tech-spec → sprint-planning → dev-story

### BMad Method Track
- **Planning**: PRD + Architecture + UX (optional)
- **Time**: 1-3 days
- **Use for**: Products, platforms, complex features
- **Workflows**: Full 4-phase approach with all planning artifacts

### Enterprise Method Track
- **Planning**: BMad Method + Security/DevOps/Test
- **Time**: 3-7 days
- **Use for**: Enterprise needs, compliance, multi-tenant systems
- **Workflows**: Extended planning with additional validation workflows

## Important Conventions

### Fresh Chat Pattern
- **Always use fresh chats for each workflow** to avoid context limitations and hallucinations
- Load the appropriate agent in a new chat before running a workflow
- This is critical for context-intensive workflows (PRD, architecture, story creation)

### Document Locations
- Planning documents (PRD, Architecture, UX): `docs/`
- Epic files: `docs/epics/`
- Story files: `docs/stories/`
- Status tracking: `docs/bmm-workflow-status.yaml`, `docs/sprint-status.yaml`

### Workflow Invocation
Agents support fuzzy matching for workflow commands:
- Shorthand: `*prd`, `*dev-story`
- Natural language: "Let's create a PRD", "Run the dev-story workflow"
- Menu selection: Select numbered menu items

### Story Lifecycle
Stories progress through defined states tracked in `sprint-status.yaml`:
- `backlog` - In epic, not yet drafted
- `drafted` - Story file created, needs context
- `ready` - Ready for development (moved to IN PROGRESS)
- `in-progress` - Currently being implemented
- `review` - Code complete, needs review
- `done` - DoD complete

### Agent Activation
Agents are activated by:
1. **Cursor/Windsurf**: Reference agent via `@bmad/{module}/agents/{agent-name}`
2. **Claude Code**: Use slash commands like `/bmad:bmm:agents:pm`
3. Loading agent markdown files directly in IDE

## Cursor Rules Integration

The `.cursor/rules/bmad/index.mdc` provides master index of all BMad components. It's configured as manual rules (`alwaysApply: true`) that are always available for reference:

- Reference modules: `@bmad/{module}`
- Reference agents: `@bmad/{module}/agents/{agent-name}`
- Reference workflows: `@bmad/{module}/workflows/{workflow-name}`
- Reference tasks: `@bmad/{module}/tasks/{task-name}`

## Working with BMad Projects

### Starting a New Project
1. Load Analyst agent in fresh chat
2. Run `workflow-init` to set up tracking and choose track
3. Follow recommended workflows from `workflow-status`
4. Use fresh chats for each planning workflow

### Continuing Existing Work
1. Load any agent in fresh chat
2. Run `workflow-status` to see current phase and next steps
3. Load appropriate agent for recommended workflow
4. Execute workflow in fresh chat

### During Implementation (Phase 4)
1. Always check `sprint-status.yaml` to see current epic/story
2. Use SM agent for story lifecycle management
3. Use DEV agent for implementation and reviews
4. Mark stories complete with `story-done` workflow

### Handling Changes
- Use `correct-course` workflow (SM agent) for scope changes
- Run `retrospective` workflow (SM agent) after epic completion
- Re-run `implementation-readiness` (Architect) after major planning changes

## Module Development

When creating custom BMad components:

1. **Agents**: Use YAML source format with persona, commands, and integration points
2. **Workflows**: Include `workflow.yaml`, `instructions.md`, and optional `template.md`
3. **Validation**: Run `audit-workflow` to ensure quality standards
4. **Documentation**: Follow BMad conventions for README structure
5. **Installation**: Modules compile to `.claude/commands/` and `.cursor/rules/` on install

## Additional Resources

- **Complete Documentation**: `.bmad/bmm/docs/README.md`
- **Quick Start Guide**: `.bmad/bmm/docs/quick-start.md`
- **Scale Adaptive System**: `.bmad/bmm/docs/scale-adaptive-system.md`
- **Agent Guide**: `.bmad/bmm/docs/agents-guide.md`
- **Community Discord**: https://discord.gg/gk8jAdXWmj
- **YouTube Tutorials**: https://www.youtube.com/@BMadCode
