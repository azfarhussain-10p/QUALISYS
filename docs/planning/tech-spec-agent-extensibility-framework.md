# QUALISYS — Agent Extensibility Framework: Technical Specification

**Product:** QUALISYS — AI System Quality Assurance Platform
**Feature:** Agent Extensibility Framework (Custom Agent Support)
**Author:** Winston (Architect Agent) | Requested by Azfar
**Date:** 2026-02-15
**Status:** Draft — Pending Architecture Board Approval
**Version:** 1.0
**Epic Alignment:** Extends Epic 6, Phase 3 (Extensibility) — Expands Story 6.5
**Architecture Reference:** Architecture v1.0 — AgentOrchestrator Abstraction (ADR-005)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Architecture Analysis: Current Extensibility](#3-architecture-analysis-current-extensibility)
4. [Gap Analysis](#4-gap-analysis)
5. [Technical Design: Agent Registry Service](#5-technical-design-agent-registry-service)
6. [Technical Design: Per-Tenant Agent Customization](#6-technical-design-per-tenant-agent-customization)
7. [Technical Design: Agent Isolation & Circuit Breakers](#7-technical-design-agent-isolation--circuit-breakers)
8. [Technical Design: Agent Versioning](#8-technical-design-agent-versioning)
9. [Database Schema](#9-database-schema)
10. [API Contracts](#10-api-contracts)
11. [Story Breakdown](#11-story-breakdown)
12. [Implementation Sequence & Dependencies](#12-implementation-sequence--dependencies)
13. [Effort Estimates](#13-effort-estimates)
14. [Risk Assessment](#14-risk-assessment)
15. [Success Metrics](#15-success-metrics)

---

## 1. Executive Summary

### The Question

> "After go-live, if a client requests a new customized agent within QUALISYS, would our current architecture support that?"

### The Answer

**Yes — the architecture supports custom agents, but the process today requires code deployment.** The `AgentOrchestrator` abstraction, generic SSE streaming endpoint, agent-agnostic RBAC, and tenant-scoped data model all enable new agents without architectural changes.

**What's missing is the operational layer** — the ability to register, configure, customize, isolate, and version agents at runtime without deploying new code. This tech spec closes that gap by formalizing four capabilities:

| # | Capability | Gap ID | Priority | Effort |
|---|-----------|--------|----------|--------|
| A | **Agent Registry Service** — Runtime agent registration and discovery | Gap A | HIGH | 2-3 weeks |
| B | **Per-Tenant Agent Customization** — Client-specific agent configuration | Gap B | HIGH | 1-2 weeks |
| C | **Agent Isolation & Circuit Breakers** — Fault containment per agent | Gap C | MEDIUM | 1 week |
| D | **Agent Versioning** — Prompt versioning with gradual rollout | Gap D | MEDIUM | 1-2 weeks |

**Total Effort:** 5-8 weeks (extends Epic 6 Phase 3)

**Strategic Value:** Transforms QUALISYS from a "product with agents" to a "platform for agents" — enabling client customization, third-party agent development, and the future Agent Marketplace (Story 6.5).

### Target User Personas (PM Clarification — F1)

Stories 6.5a-d target **two specific personas** in Phase 1:

| Persona | Role | What They Do | Stories |
|---------|------|-------------|---------|
| **Platform Admin** (QUALISYS internal) | Owner/Admin (platform-level) | Register new agents, manage global definitions, version prompts, monitor circuit breakers | 6.5a, 6.5c, 6.5d |
| **Tenant Admin** (Client organization) | Owner/Admin (tenant-level) | Enable/disable agents for their org, customize prompts, override LLM provider | 6.5b |

**Explicitly out of scope for Phase 1:**
- External developers building agents via SDK (→ original Story 6.5, Phase 2)
- Marketplace users discovering/installing community agents (→ original Story 6.5, Phase 2)
- Non-technical users configuring agents via wizard (→ future consideration)

This scope boundary prevents gold-plating the admin UI and keeps Phase 1 focused on the operational foundation.

---

## 2. Problem Statement

### Current State

Adding a new agent to QUALISYS today requires:

1. Writing a new Python service file (`services/agents/<agent_name>.py`)
2. Defining a system prompt and LangChain chain
3. Registering the agent in orchestrator configuration (code change)
4. Creating database migrations for agent-specific tables
5. Adding RBAC permissions (code change)
6. Adding frontend UI components (Agent Card, output renderers)
7. Deploying the full application

**This is a code deployment, not a configuration change.** For internal agents (our 7 built-in agents), this is acceptable. For client-requested custom agents post-go-live, this creates several problems:

- **Lead time:** 5-9 weeks per custom agent (design → develop → test → deploy)
- **Deployment coupling:** Custom agent deployment requires full platform release
- **No tenant isolation:** All tenants get all agents; cannot enable/disable per client
- **No customization:** Same system prompt for all tenants; no client-specific tuning
- **No fault isolation:** A misbehaving agent affects all tenants
- **No versioning:** Prompt updates apply to all tenants simultaneously

### Target State

- Register new agents via API or admin UI (no code deployment for simple agents)
- Enable/disable agents per tenant
- Customize agent prompts, output templates, and approval workflows per tenant
- Isolate agent failures so one agent cannot degrade others
- Version agent prompts with gradual rollout and rollback

---

## 3. Architecture Analysis: Current Extensibility

### What Already Supports Custom Agents

| Component | Extensibility | Evidence |
|-----------|--------------|---------|
| **AgentOrchestrator Interface** | ✅ Agent-agnostic routing by `agentId` | ADR-005: `executeAgent(agentId, context)` |
| **SSE Streaming Endpoint** | ✅ Generic `/agents/{agent_id}/stream` | Architecture: Novel Pattern #2 (Conversation Threading) |
| **RBAC Model** | ✅ Permissions reference `agent_id` string, not hardcoded enum | Agent Specs: Cross-Agent RBAC Matrix |
| **Governance Gates** | ✅ Approval workflows configured per agent | Agent Specs: 15 gates, agent-configurable |
| **RAG Layer** | ✅ Tag-based filtering is agent-agnostic | Architecture: pgvector with metadata filters |
| **Token Budgeting** | ✅ Per-tenant, applies to all LLM calls | Architecture: Redis atomic counters |
| **Frontend Agent Cards** | ✅ Data-driven rendering (agent name, description, icon) | Architecture: Conversational UI pattern |
| **Database** | ✅ Schema-per-tenant supports any new tables | Architecture: Multi-Tenant Schema Routing |
| **Multi-Provider LLM** | ✅ AgentOrchestrator routes to OpenAI/Anthropic/vLLM | Architecture: LLM Provider Strategy |

### What's Missing

| Component | Gap | Impact |
|-----------|-----|--------|
| **Agent Registry** | Agents hardcoded in config | Cannot add agents without deployment |
| **Tenant Agent Config** | No per-tenant overrides | All tenants get identical agents |
| **Agent Circuit Breakers** | No per-agent fault isolation | One agent failure cascades |
| **Agent Versioning** | No prompt version management | No safe rollout or rollback |
| **Admin UI for Agents** | No self-service agent management | Requires engineering intervention |

---

## 4. Gap Analysis

### Gap A: Agent Registry Service (Priority: HIGH)

**Problem:** Agent definitions are embedded in application code and configuration files. There is no runtime service that knows "what agents exist."

**Impact:** Every new agent requires code deployment. Cannot dynamically discover available agents. Cannot enable/disable agents without code changes.

**Solution:** A lightweight registry service that stores agent metadata and serves agent discovery queries.

### Gap B: Per-Tenant Agent Customization (Priority: HIGH)

**Problem:** All tenants receive identical agent behavior. Enterprise clients need customized prompts, output formats, and approval workflows.

**Impact:** Cannot differentiate service for enterprise clients. Cannot offer "premium" agent configurations. Cannot accommodate industry-specific requirements (HIPAA prompts for healthcare clients).

**Solution:** A tenant-agent configuration layer that allows per-tenant overrides of system prompts, output templates, and governance rules.

### Gap C: Agent Isolation & Circuit Breakers (Priority: MEDIUM)

**Problem:** All agents share the same execution context. A runaway agent (infinite prompt loop, excessive token consumption) impacts all other agents and all tenants.

**Impact:** Single point of failure. One bad agent can degrade the entire platform.

**Solution:** Per-agent circuit breakers, token budgets, and timeout enforcement.

### Gap D: Agent Versioning (Priority: MEDIUM)

**Problem:** Agent prompts and behavior have no version management. Updates affect all tenants immediately with no rollback capability.

**Impact:** Cannot safely iterate on agent quality. Cannot A/B test prompt improvements. Cannot rollback bad updates.

**Solution:** Version tracking for agent definitions with tenant-pinnable versions and gradual rollout support.

---

## 5. Technical Design: Agent Registry Service

### 5.1 Overview

The Agent Registry is a **lightweight service** (not a separate microservice — it's a module within the existing FastAPI backend) that manages agent definitions at runtime.

**Design Decision:** Implement as a backend module (`services/agent_registry/`) within the existing monorepo, not as a separate microservice. This avoids operational overhead while achieving the runtime registration goal. If/when we extract microservices (Phase 2 architecture plan), it becomes a candidate for extraction.

### 5.2 Agent Definition Model

```python
# models/agent_definition.py
from pydantic import BaseModel
from enum import Enum

class AgentType(str, Enum):
    BUILTIN = "builtin"        # Our 7 standard agents
    CUSTOM = "custom"          # Client-built via SDK
    MARKETPLACE = "marketplace" # Community agents (future)

class AgentPhase(str, Enum):
    MVP = "mvp"
    POST_MVP = "post_mvp"
    CUSTOM = "custom"

class AgentDefinition(BaseModel):
    agent_id: str                     # e.g., "baconsultant", "compliance-auditor"
    name: str                         # Display name
    description: str                  # What this agent does
    type: AgentType                   # builtin | custom | marketplace
    phase: AgentPhase                 # mvp | post_mvp | custom
    version: str                      # Semantic version "1.0.0"
    system_prompt: str                # Base system prompt
    llm_provider: str                 # "openai" | "anthropic" | "vllm"
    llm_model: str                    # "gpt-4" | "claude-3-sonnet" etc.
    max_tokens_per_invocation: int    # Token budget per call
    timeout_seconds: int              # Hard timeout
    input_types: list[str]            # ["pdf", "docx", "markdown"]
    output_schema: dict               # JSON schema for agent output
    required_roles: list[str]         # RBAC: which roles can invoke
    approval_gates: list[dict]        # Governance configuration
    tags: list[str]                   # For RAG filtering, categorization
    icon: str                         # Frontend icon identifier
    enabled: bool = True              # Global enable/disable
```

### 5.3 Registry Operations

```python
# services/agent_registry/registry.py
class AgentRegistry:
    """Runtime agent registration and discovery."""

    async def register(self, definition: AgentDefinition) -> AgentDefinition:
        """Register a new agent or update existing."""
        # Validate definition (prompt length, schema, roles exist)
        # Store in database
        # Invalidate Redis cache
        # Return registered definition

    async def get(self, agent_id: str) -> AgentDefinition:
        """Get agent definition by ID. Cache-first (Redis, 1h TTL)."""

    async def discover(
        self,
        tenant_id: UUID,
        role: str = None,
        tags: list[str] = None,
        include_disabled: bool = False
    ) -> list[AgentDefinition]:
        """Discover agents available for a tenant+role combination."""
        # 1. Get all globally enabled agents
        # 2. Filter by tenant_agent_config (enabled per tenant)
        # 3. Filter by role (RBAC check)
        # 4. Filter by tags if provided
        # 5. Return filtered list

    async def disable(self, agent_id: str) -> None:
        """Globally disable an agent (emergency kill switch)."""

    async def list_all(self) -> list[AgentDefinition]:
        """Admin: list all registered agents."""
```

### 5.4 Orchestrator Integration

The existing `AgentOrchestrator` gains a registry dependency:

```python
# services/agents/orchestrator.py (MODIFIED)
class AgentOrchestrator:
    def __init__(self, registry: AgentRegistry, ...):
        self.registry = registry

    async def execute_agent(self, agent_id: str, context: ProjectContext):
        # NEW: Resolve agent from registry (not hardcoded config)
        agent_def = await self.registry.get(agent_id)
        if not agent_def or not agent_def.enabled:
            raise AgentNotFoundError(agent_id)

        # Existing: Build LangChain chain / custom chain
        chain = self._build_chain(agent_def)

        # Existing: Execute with context
        result = await chain.ainvoke(context)
        return result
```

### 5.5 Caching Strategy

- **Redis cache:** Agent definitions cached with 1-hour TTL
- **Cache key:** `agent_def:{agent_id}` for individual lookups
- **Cache key:** `agent_discovery:{tenant_id}:{role}` for discovery queries
- **Cache invalidation:** On register/update/disable, delete related keys
- **Fallback:** Database query on cache miss

---

## 6. Technical Design: Per-Tenant Agent Customization

### 6.1 Overview

Enterprise clients need the ability to customize agents for their specific context. This layer sits between the global agent definition (registry) and the runtime execution.

### 6.2 Customization Model

```python
# models/tenant_agent_config.py
class PromptOverrideMode(str, Enum):
    APPEND = "append"      # Add to end of base prompt
    PREPEND = "prepend"    # Add to start of base prompt
    REPLACE = "replace"    # Fully replace base prompt (advanced)

class TenantAgentConfig(BaseModel):
    tenant_id: UUID
    agent_id: str
    enabled: bool = True                          # Per-tenant enable/disable
    custom_prompt: str | None = None              # Prompt customization
    prompt_override_mode: PromptOverrideMode = PromptOverrideMode.APPEND
    custom_output_template: dict | None = None    # Output format override
    approval_workflow_override: dict | None = None # Custom approval gates
    max_tokens_override: int | None = None        # Tenant-specific token limit
    llm_provider_override: str | None = None      # Use different LLM
    llm_model_override: str | None = None         # Use different model
    pinned_version: str | None = None             # Pin to specific agent version
    custom_tags: list[str] = []                   # Additional RAG tags
    metadata: dict = {}                           # Arbitrary config
```

### 6.3 Resolution Logic

When an agent is invoked for a tenant, the system resolves the effective configuration:

```python
# services/agent_registry/resolver.py
class AgentConfigResolver:
    """Resolves effective agent config by merging global + tenant overrides."""

    async def resolve(self, agent_id: str, tenant_id: UUID) -> ResolvedAgentConfig:
        # 1. Get base agent definition from registry
        base = await self.registry.get(agent_id)

        # 2. Get tenant-specific overrides (if any)
        tenant_config = await self.get_tenant_config(tenant_id, agent_id)

        # 3. Check tenant-level enabled flag
        if tenant_config and not tenant_config.enabled:
            raise AgentDisabledForTenantError(agent_id, tenant_id)

        # 4. Resolve version (tenant pin > latest)
        version = tenant_config.pinned_version if tenant_config else base.version

        # 5. Resolve system prompt (merge strategy)
        system_prompt = self._resolve_prompt(base, tenant_config)

        # 6. Resolve LLM provider (tenant override > base)
        llm_provider = (tenant_config.llm_provider_override
                        if tenant_config and tenant_config.llm_provider_override
                        else base.llm_provider)

        # 7. Resolve token budget (min of base and tenant override)
        max_tokens = min(
            base.max_tokens_per_invocation,
            tenant_config.max_tokens_override or base.max_tokens_per_invocation
        )

        return ResolvedAgentConfig(
            agent_id=agent_id,
            version=version,
            system_prompt=system_prompt,
            llm_provider=llm_provider,
            llm_model=llm_model,
            max_tokens=max_tokens,
            approval_gates=approval_gates,
            output_template=output_template,
        )

    def _resolve_prompt(self, base: AgentDefinition,
                        tenant: TenantAgentConfig | None) -> str:
        if not tenant or not tenant.custom_prompt:
            return base.system_prompt

        if tenant.prompt_override_mode == PromptOverrideMode.APPEND:
            return f"{base.system_prompt}\n\n## Client-Specific Instructions\n\n{tenant.custom_prompt}"
        elif tenant.prompt_override_mode == PromptOverrideMode.PREPEND:
            return f"{tenant.custom_prompt}\n\n{base.system_prompt}"
        elif tenant.prompt_override_mode == PromptOverrideMode.REPLACE:
            return tenant.custom_prompt
```

### 6.4 Admin UI Touchpoints

- **Platform Admin (Owner/Admin):** Can manage global agent definitions (register, update, disable)
- **Tenant Admin (Owner/Admin per tenant):** Can configure per-tenant agent settings (enable/disable, custom prompts, LLM override)
- **Self-service UI:** Settings → Agents → [agent card] → "Customize" button

---

## 7. Technical Design: Agent Isolation & Circuit Breakers

### 7.1 Overview

Each agent execution must be isolated so that failures (timeouts, excessive token usage, error loops) in one agent cannot cascade to other agents or other tenants.

### 7.2 Three Isolation Layers

**Layer 1: Token Budget (Per-Agent, Per-Tenant)**

```python
# services/agents/token_guard.py
class AgentTokenGuard:
    """Enforces per-agent token budgets using Redis atomic counters."""

    async def check_budget(self, agent_id: str, tenant_id: UUID,
                           estimated_tokens: int) -> bool:
        key = f"token_budget:{tenant_id}:{agent_id}:{today()}"
        current = await self.redis.get(key) or 0
        limit = await self.get_agent_token_limit(agent_id, tenant_id)

        if int(current) + estimated_tokens > limit:
            raise AgentTokenBudgetExceeded(agent_id, tenant_id, limit)
        return True

    async def record_usage(self, agent_id: str, tenant_id: UUID,
                           tokens_used: int):
        key = f"token_budget:{tenant_id}:{agent_id}:{today()}"
        await self.redis.incrby(key, tokens_used)
        await self.redis.expire(key, 86400)  # 24h TTL
```

**Layer 2: Timeout Enforcement (Per-Agent)**

```python
# services/agents/timeout_guard.py
import asyncio

class AgentTimeoutGuard:
    """Hard timeout per agent invocation."""

    async def execute_with_timeout(self, agent_id: str, coro,
                                    timeout_seconds: int):
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            await self.metrics.increment("agent_timeout_total",
                                          labels={"agent_id": agent_id})
            raise AgentTimeoutError(agent_id, timeout_seconds)
```

**Layer 3: Circuit Breaker (Per-Agent)**

```python
# services/agents/circuit_breaker.py
class AgentCircuitBreaker:
    """Per-agent circuit breaker. Opens when error rate exceeds threshold."""

    FAILURE_THRESHOLD = 5       # Failures in window before circuit opens
    RECOVERY_TIMEOUT = 60       # Seconds before half-open attempt
    WINDOW_SIZE = 120           # Sliding window in seconds

    async def call(self, agent_id: str, func, *args, **kwargs):
        state = await self._get_state(agent_id)

        if state == "open":
            if await self._should_attempt_recovery(agent_id):
                # Half-open: try one request
                return await self._attempt_half_open(agent_id, func,
                                                      *args, **kwargs)
            raise AgentCircuitOpenError(agent_id)

        try:
            result = await func(*args, **kwargs)
            await self._record_success(agent_id)
            return result
        except Exception as e:
            await self._record_failure(agent_id)
            if await self._should_open(agent_id):
                await self._open_circuit(agent_id)
                await self.alert_service.notify(
                    f"Circuit breaker OPENED for agent {agent_id}"
                )
            raise
```

### 7.3 Combined Execution Guard

```python
# services/agents/execution_guard.py
class AgentExecutionGuard:
    """Wraps all three isolation layers into a single execution guard."""

    def __init__(self, token_guard, timeout_guard, circuit_breaker):
        self.token_guard = token_guard
        self.timeout_guard = timeout_guard
        self.circuit_breaker = circuit_breaker

    async def guarded_execute(self, agent_id: str, tenant_id: UUID,
                               agent_config: ResolvedAgentConfig,
                               execute_fn):
        # 1. Check circuit breaker
        # 2. Check token budget
        await self.token_guard.check_budget(
            agent_id, tenant_id, agent_config.max_tokens
        )

        # 3. Execute with timeout + circuit breaker
        async def _execute():
            return await self.timeout_guard.execute_with_timeout(
                agent_id, execute_fn(), agent_config.timeout_seconds
            )

        result = await self.circuit_breaker.call(agent_id, _execute)

        # 4. Record actual token usage
        await self.token_guard.record_usage(
            agent_id, tenant_id, result.tokens_used
        )

        return result
```

---

## 8. Technical Design: Agent Versioning

### 8.1 Overview

Agent definitions (especially system prompts) evolve over time. Versioning enables safe iteration without breaking existing tenant workflows.

### 8.2 Version Model

```python
# models/agent_version.py
class AgentVersion(BaseModel):
    agent_id: str
    version: str               # Semantic version "1.2.0"
    system_prompt: str         # Prompt for this version
    output_schema: dict        # Output schema for this version
    changelog: str             # What changed
    created_at: datetime
    status: str                # "active" | "deprecated" | "retired"
    rollout_percentage: int    # 0-100, for gradual rollout
```

### 8.3 Version Resolution

```python
# services/agent_registry/version_resolver.py
class AgentVersionResolver:
    """Resolves which agent version to use for a given request."""

    async def resolve_version(self, agent_id: str, tenant_id: UUID) -> str:
        # 1. Check tenant pin (highest priority)
        tenant_config = await self.get_tenant_config(tenant_id, agent_id)
        if tenant_config and tenant_config.pinned_version:
            return tenant_config.pinned_version

        # 2. Get all active versions
        versions = await self.get_active_versions(agent_id)

        # 3. If any version has rollout_percentage < 100, use weighted selection
        latest = versions[0]  # Sorted by version descending
        if latest.rollout_percentage < 100:
            # Deterministic selection based on tenant_id hash
            # (same tenant always gets same version for consistency)
            bucket = hash(str(tenant_id)) % 100
            if bucket < latest.rollout_percentage:
                return latest.version
            else:
                # Fall back to previous stable version
                return versions[1].version if len(versions) > 1 else latest.version

        return latest.version
```

### 8.4 Rollout Strategy

1. **New version created** at `rollout_percentage = 10` (10% of tenants)
2. **Monitor metrics** for 48 hours (error rate, output quality, token usage)
3. **Increase to 50%** if metrics are stable
4. **Full rollout to 100%** after validation
5. **Previous version** marked as `deprecated` (still available for pinned tenants)
6. **Retirement** after 90 days (tenants pinned to retired version auto-upgraded with notification)

---

## 9. Database Schema

### 9.1 New Tables

```sql
-- Agent definitions (global registry)
-- Location: public schema (shared across tenants)
CREATE TABLE agent_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    type VARCHAR(20) NOT NULL DEFAULT 'builtin',  -- builtin | custom | marketplace
    phase VARCHAR(20) NOT NULL DEFAULT 'custom',   -- mvp | post_mvp | custom
    current_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    llm_provider VARCHAR(50) NOT NULL DEFAULT 'openai',
    llm_model VARCHAR(100) NOT NULL DEFAULT 'gpt-4',
    max_tokens_per_invocation INTEGER NOT NULL DEFAULT 10000,
    timeout_seconds INTEGER NOT NULL DEFAULT 120,
    input_types JSONB NOT NULL DEFAULT '[]',
    output_schema JSONB NOT NULL DEFAULT '{}',
    required_roles JSONB NOT NULL DEFAULT '[]',
    approval_gates JSONB NOT NULL DEFAULT '[]',
    tags JSONB NOT NULL DEFAULT '[]',
    icon VARCHAR(100) DEFAULT 'default-agent',
    enabled BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Agent versions (prompt history and rollout management)
-- Location: public schema
CREATE TABLE agent_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(100) NOT NULL REFERENCES agent_definitions(agent_id),
    version VARCHAR(20) NOT NULL,
    system_prompt TEXT NOT NULL,
    output_schema JSONB NOT NULL DEFAULT '{}',
    changelog TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active | deprecated | retired
    rollout_percentage INTEGER NOT NULL DEFAULT 100 CHECK (rollout_percentage BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retired_at TIMESTAMPTZ,
    UNIQUE(agent_id, version)
);

-- Per-tenant agent configuration overrides
-- Location: public schema (references tenant_id, not tenant-scoped schema)
CREATE TABLE tenant_agent_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    agent_id VARCHAR(100) NOT NULL REFERENCES agent_definitions(agent_id),
    enabled BOOLEAN NOT NULL DEFAULT true,
    custom_prompt TEXT,
    prompt_override_mode VARCHAR(20) DEFAULT 'append',  -- append | prepend | replace
    custom_output_template JSONB,
    approval_workflow_override JSONB,
    max_tokens_override INTEGER,
    llm_provider_override VARCHAR(50),
    llm_model_override VARCHAR(100),
    pinned_version VARCHAR(20),
    custom_tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, agent_id)
);

-- Agent execution metrics (for circuit breaker and observability)
-- Location: public schema, partitioned by month
CREATE TABLE agent_execution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(100) NOT NULL,
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    version VARCHAR(20) NOT NULL,
    tokens_used INTEGER,
    execution_time_ms INTEGER,
    status VARCHAR(20) NOT NULL,  -- success | error | timeout | circuit_open
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Create monthly partitions (automated via pg_partman or cron)
CREATE TABLE agent_execution_log_2026_03 PARTITION OF agent_execution_log
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

-- Indexes
CREATE INDEX idx_agent_versions_agent_status ON agent_versions(agent_id, status);
CREATE INDEX idx_tenant_agent_configs_tenant ON tenant_agent_configs(tenant_id);
CREATE INDEX idx_agent_execution_log_agent_tenant ON agent_execution_log(agent_id, tenant_id, created_at);
```

### 9.2 Seed Data for Built-in Agents

```sql
-- Register 7 built-in agents
INSERT INTO agent_definitions (agent_id, name, description, type, phase, required_roles, tags) VALUES
('baconsultant', 'BAConsultant AI Agent', 'Requirements analysis → test-ready user stories', 'builtin', 'mvp', '["owner", "admin", "pm_csm", "qa_automation"]', '["requirements", "user-stories", "gap-analysis"]'),
('qaconsultant', 'QAConsultant AI Agent', 'Test strategy, manual checklists, BDD scenarios', 'builtin', 'mvp', '["owner", "admin", "pm_csm", "qa_automation", "qa_manual"]', '["test-strategy", "bdd", "test-cases"]'),
('automationconsultant', 'AutomationConsultant AI Agent', 'Automated scripts, framework architecture, self-healing', 'builtin', 'mvp', '["owner", "admin", "qa_automation", "dev"]', '["playwright", "automation", "self-healing"]'),
('logreader', 'AI Log Reader/Summarizer', 'Log analysis, error pattern detection, negative tests', 'builtin', 'post_mvp', '["owner", "admin", "qa_automation", "dev"]', '["logs", "error-patterns", "negative-testing"]'),
('securityscanner', 'Security Scanner Orchestrator', 'Vulnerability scanning, OWASP Top 10', 'builtin', 'post_mvp', '["owner", "admin", "qa_automation"]', '["security", "owasp", "vulnerability"]'),
('performanceagent', 'Performance/Load Agent', 'Load/stress testing, bottleneck identification', 'builtin', 'post_mvp', '["owner", "admin", "qa_automation"]', '["performance", "load-testing", "k6"]'),
('dbconsultant', 'DatabaseConsultant AI Agent', 'Schema validation, data integrity, ETL validation', 'builtin', 'post_mvp', '["owner", "admin", "qa_automation", "dev"]', '["database", "schema", "etl", "performance"]');
```

---

## 10. API Contracts

### 10.1 Agent Registry APIs

```
# Agent Management (Platform Admin only)
GET    /api/v1/admin/agents                    # List all agents
POST   /api/v1/admin/agents                    # Register new agent
GET    /api/v1/admin/agents/{agent_id}         # Get agent definition
PUT    /api/v1/admin/agents/{agent_id}         # Update agent definition
DELETE /api/v1/admin/agents/{agent_id}         # Disable agent (soft delete)

# Agent Versions (Platform Admin only)
GET    /api/v1/admin/agents/{agent_id}/versions           # List versions
POST   /api/v1/admin/agents/{agent_id}/versions           # Create new version
PUT    /api/v1/admin/agents/{agent_id}/versions/{version} # Update rollout %

# Agent Discovery (All authenticated users)
GET    /api/v1/agents                          # Discover available agents (tenant+role filtered)
GET    /api/v1/agents/{agent_id}               # Get agent info (if authorized)
```

### 10.2 Tenant Agent Configuration APIs

```
# Tenant Agent Config (Tenant Owner/Admin only)
GET    /api/v1/tenant/agents                           # List agent configs for tenant
GET    /api/v1/tenant/agents/{agent_id}/config         # Get tenant config for agent
PUT    /api/v1/tenant/agents/{agent_id}/config         # Update tenant config
DELETE /api/v1/tenant/agents/{agent_id}/config         # Reset to defaults
```

### 10.3 Agent Metrics APIs

```
# Agent Observability (Admin + QA-Automation)
GET    /api/v1/agents/{agent_id}/metrics               # Execution metrics (last 24h)
GET    /api/v1/agents/{agent_id}/circuit-breaker        # Circuit breaker status
POST   /api/v1/admin/agents/{agent_id}/circuit-breaker/reset  # Manual reset (Admin)
```

---

## 11. Story Breakdown

These stories extend **Epic 6, Phase 3 (Extensibility)** and expand the scope of **Story 6.5 (Agent SDK & Marketplace)** into a multi-story capability.

### Story 6.5a: Agent Registry Service

**As a** platform administrator,
**I want** to register, discover, and manage agent definitions at runtime,
**so that** new agents can be added to QUALISYS without code deployment.

**AC1: Database Schema** — `agent_definitions` and `agent_versions` tables created via Alembic migration. 7 built-in agents seeded on first deployment. Migration is idempotent (re-running does not duplicate seed data). `agent_execution_log` table partitioned by month with retention policy: **1 year hot data** (PostgreSQL partitions), **7 years cold data** (archived to S3/Azure Blob as compressed Parquet files, aligned with SOC 2 audit trail retention per Story 6.7).

**AC2: Registry Service** — `AgentRegistry` class implements `register()`, `get()`, `discover()`, `disable()`, `list_all()` methods. All methods validate input using Pydantic models. Redis caching with 1-hour TTL for `get()` and `discover()` queries. Cache invalidated on register/update/disable.

**AC3: Orchestrator Integration** — `AgentOrchestrator.execute_agent()` resolves agent definition from registry instead of hardcoded configuration. If agent not found or disabled, returns HTTP 404 with structured error. Existing 7 agents continue to function identically (zero regression).

**AC4: Admin API Endpoints** — CRUD endpoints at `/api/v1/admin/agents` with Pydantic request/response schemas. Endpoints require `owner` or `admin` role. Input validation: `agent_id` is URL-safe slug (lowercase alphanumeric + hyphens), `system_prompt` max 50,000 characters, `max_tokens_per_invocation` between 100 and 200,000.

**AC5: Agent Discovery API** — `GET /api/v1/agents` returns list of agents available to the requesting user's tenant + role combination. Response excludes `system_prompt` (Level 1 metadata only: id, name, description, tags, icon). Response cached per tenant+role in Redis (5 min TTL).

**AC6: Version Management** — `agent_versions` table tracks prompt versions. Creating a new version auto-increments minor version. Previous versions retained for rollback. Admin can set `rollout_percentage` (0-100) for gradual rollout.

**Tasks:**
- [ ] Task 1: Alembic migration for `agent_definitions` and `agent_versions` tables + seed data (AC: #1)
- [ ] Task 2: SQLAlchemy models for `AgentDefinition` and `AgentVersion` (AC: #1)
- [ ] Task 3: `AgentRegistry` service class with Redis caching (AC: #2)
- [ ] Task 4: Modify `AgentOrchestrator` to use registry (AC: #3)
- [ ] Task 5: Admin API endpoints with Pydantic schemas and RBAC (AC: #4)
- [ ] Task 6: Agent discovery API endpoint (AC: #5)
- [ ] Task 7: Version management API endpoints (AC: #6)
- [ ] Task 8: Unit tests for registry service (AC: #2, #3)
- [ ] Task 9: Integration tests for orchestrator + registry (AC: #3)
- [ ] Task 10: Integration tests for API endpoints (AC: #4, #5, #6)

**Estimate:** 2-3 weeks

---

### Story 6.5b: Per-Tenant Agent Customization

**As a** tenant administrator,
**I want** to customize agent behavior for my organization (prompts, output templates, enable/disable),
**so that** agents are tailored to my industry and testing requirements.

**AC1: Database Schema** — `tenant_agent_configs` table created via Alembic migration. Unique constraint on `(tenant_id, agent_id)`. Schema follows existing tenant isolation patterns (table in public schema, tenant_id column for RLS).

**AC2: Config Resolution** — `AgentConfigResolver` class merges global agent definition with tenant-specific overrides. Resolution order: tenant pin > tenant override > global default. Prompt merge supports three modes: `append` (default), `prepend`, `replace`. Resolved config cached in Redis (5 min TTL, invalidated on config update).

**AC3: Prompt Customization** — Tenant admin can set `custom_prompt` text. In `append` mode (default), custom prompt appended after `\n\n## Client-Specific Instructions\n\n`. In `replace` mode, full prompt replaced (warning shown in UI). Custom prompt max 10,000 characters.

**AC4: Agent Enable/Disable** — Tenant admin can disable any agent for their organization. Disabled agents do not appear in agent discovery for that tenant. Disabling an agent does not affect other tenants.

**AC5: LLM Override** — Tenant admin can override `llm_provider` and `llm_model` per agent. Validation: only providers configured for the platform (openai, anthropic, vllm) are accepted. Override shown in agent card UI with visual indicator.

**AC6: Tenant Config API** — CRUD endpoints at `/api/v1/tenant/agents/{agent_id}/config`. Requires `owner` or `admin` role within the tenant. Tenant context extracted from JWT (existing middleware). Config changes take effect within 5 minutes (cache TTL).

**AC7: Admin UI** — Settings → Agents page shows all available agents as cards. Each card shows: agent name, description, status (enabled/disabled toggle), "Customize" button. Customize modal: prompt customization field (textarea), LLM override dropdowns, version pin selector.

**AC8: Replace Mode Restrictions (PM Review — F2)** — `replace` prompt override mode is only available to tenants on Enterprise tier (controlled via feature flag `TENANT_PROMPT_REPLACE_ENABLED`). Standard-tier tenants can only use `append` or `prepend`. When `replace` mode is used, system logs a `prompt_override_replace` audit event. Support team can view a tenant's custom prompt via admin API to diagnose quality issues.

**AC9: Prompt Validation (PM Review — F2)** — Custom prompts are validated on save (not on execution) for: minimum length (50 characters), no prompt injection patterns (regex filter for "ignore previous instructions", "disregard above", "system: " prefix), UTF-8 encoding only, and max length (10,000 characters). Validation errors return structured error with specific failing rule.

**Tasks:**
- [ ] Task 1: Alembic migration for `tenant_agent_configs` table (AC: #1)
- [ ] Task 2: SQLAlchemy model for `TenantAgentConfig` (AC: #1)
- [ ] Task 3: `AgentConfigResolver` service with prompt merge logic (AC: #2, #3)
- [ ] Task 4: Integrate resolver into `AgentOrchestrator` execution flow (AC: #2)
- [ ] Task 5: Tenant config API endpoints with RBAC (AC: #6)
- [ ] Task 6: Agent enable/disable logic in discovery service (AC: #4)
- [ ] Task 7: LLM override validation and routing (AC: #5)
- [ ] Task 8: Replace mode tier gating + feature flag (AC: #8)
- [ ] Task 9: Prompt validation service with injection pattern detection (AC: #9)
- [ ] Task 10: React admin UI — agent list page with enable/disable toggles (AC: #7)
- [ ] Task 11: React admin UI — customization modal (prompt, LLM, version) (AC: #7)
- [ ] Task 12: Unit tests for config resolver and prompt merge (AC: #2, #3)
- [ ] Task 13: Unit tests for prompt validation and injection detection (AC: #9)
- [ ] Task 14: Integration tests for tenant-scoped behavior (AC: #4, #6)
- [ ] Task 15: E2E test: customize agent for tenant A, verify tenant B unaffected (AC: #4)

**Estimate:** 2-3 weeks (1.5 weeks backend, 1 week frontend)

---

### Story 6.5c: Agent Isolation & Circuit Breakers

**As a** platform operator,
**I want** per-agent fault isolation (token budgets, timeouts, circuit breakers),
**so that** one misbehaving agent cannot degrade the platform for other agents or tenants.

**AC1: Per-Agent Token Budget** — `AgentTokenGuard` enforces daily token limits per agent per tenant. Token usage tracked in Redis atomic counters (key: `token_budget:{tenant_id}:{agent_id}:{date}`). When budget exceeded, agent invocation returns HTTP 429 with `Retry-After: <seconds until midnight UTC>`. Default budget: `max_tokens_per_invocation × 100` per day (configurable).

**AC2: Per-Agent Timeout** — `AgentTimeoutGuard` enforces hard timeout per agent invocation. Timeout value from agent definition (default: 120 seconds). On timeout, LLM call cancelled, execution logged as `status=timeout`, HTTP 504 returned. Timeout metric emitted: `agent_timeout_total{agent_id}`.

**AC3: Per-Agent Circuit Breaker** — `AgentCircuitBreaker` implements three states: closed (normal), open (blocking), half-open (testing). Circuit opens when 5 failures occur within 120-second sliding window. Open circuit returns HTTP 503 with structured error. Half-open state attempts 1 request after 60 seconds. On success: close circuit. On failure: re-open. Circuit state stored in Redis. State change emits Prometheus metric `agent_circuit_state{agent_id, state}`.

**AC4: Execution Guard** — `AgentExecutionGuard` wraps all three isolation layers. Order: circuit breaker check → token budget check → timeout-wrapped execution → record usage. Guard integrated into `AgentOrchestrator.execute_agent()`. All existing agents pass through guard (no bypass).

**AC5: Manual Circuit Breaker Reset** — Admin API endpoint `POST /api/v1/admin/agents/{agent_id}/circuit-breaker/reset` allows manual reset of a tripped circuit breaker. Requires `owner` or `admin` role. Reset logged in audit trail.

**AC6: Monitoring Dashboard** — Grafana dashboard panel: "Agent Health" showing per-agent circuit breaker status (green/yellow/red), token consumption (bar chart), timeout rate (line chart), error rate (line chart). Alert rules: circuit breaker open → PagerDuty P2, token budget >90% → Slack notification.

**Tasks:**
- [ ] Task 1: `AgentTokenGuard` with Redis atomic counters (AC: #1)
- [ ] Task 2: `AgentTimeoutGuard` with asyncio.wait_for (AC: #2)
- [ ] Task 3: `AgentCircuitBreaker` with Redis state management (AC: #3)
- [ ] Task 4: `AgentExecutionGuard` combining all three layers (AC: #4)
- [ ] Task 5: Integrate execution guard into orchestrator (AC: #4)
- [ ] Task 6: Admin API for circuit breaker reset (AC: #5)
- [ ] Task 7: Prometheus metrics for all three isolation layers (AC: #6)
- [ ] Task 8: Grafana dashboard panel configuration (AC: #6)
- [ ] Task 9: Alert rules (circuit breaker, token budget) (AC: #6)
- [ ] Task 10: Unit tests for each isolation layer (AC: #1-3)
- [ ] Task 11: Integration test: simulate agent failure, verify circuit opens (AC: #3)
- [ ] Task 12: Integration test: verify one agent's circuit break doesn't affect others (AC: #4)

**Estimate:** 1.5-2 weeks

---

### Story 6.5d: Agent Prompt Versioning & Gradual Rollout

**As a** platform administrator,
**I want** to version agent prompts and roll out changes gradually,
**so that** prompt improvements can be validated before affecting all tenants.

**AC1: Version Creation** — Admin can create a new version for any agent via API or admin UI. New version requires: `system_prompt`, `changelog`. Version auto-incremented (1.0.0 → 1.1.0 for minor, 2.0.0 for major). Previous version retained (never deleted).

**AC2: Gradual Rollout** — New versions created with `rollout_percentage` (default: 10). Percentage determines what fraction of tenants receive the new version. Tenant assignment is deterministic (based on `hash(tenant_id) % 100`) so same tenant consistently gets same version within a rollout window.

**AC3: Version Resolution** — `AgentVersionResolver` resolves effective version using priority: (1) tenant pinned version, (2) rollout-weighted latest version, (3) stable latest version. Resolution logged in `agent_execution_log` for traceability.

**AC4: Rollback** — Admin can set `rollout_percentage = 0` to effectively rollback a version. Admin can also mark a version as `deprecated` (still usable by pinned tenants) or `retired` (force upgrade). Tenants pinned to retired version receive notification and are auto-upgraded to latest active version.

**AC5: Version Comparison Metrics** — `agent_execution_log` tracks `version` column per invocation. Grafana dashboard shows side-by-side comparison: error rate, token usage, execution time by version. Enables data-driven rollout decisions.

**AC6: Admin UI — Version Management** — Admin → Agents → [agent] → "Versions" tab. Shows: version list with status (active/deprecated/retired), rollout percentage slider, changelog, "Create New Version" button, "Compare Metrics" link.

**Tasks:**
- [ ] Task 1: Version creation API with auto-increment logic (AC: #1)
- [ ] Task 2: `AgentVersionResolver` with deterministic tenant bucketing (AC: #2, #3)
- [ ] Task 3: Integrate version resolver into config resolution pipeline (AC: #3)
- [ ] Task 4: Rollback API (set rollout %, deprecate, retire) (AC: #4)
- [ ] Task 5: Add `version` column to `agent_execution_log` (AC: #5)
- [ ] Task 6: Grafana dashboard: version comparison panel (AC: #5)
- [ ] Task 7: React admin UI: version list, rollout slider, create version form (AC: #6)
- [ ] Task 8: Tenant notification on version retirement (AC: #4)
- [ ] Task 9: Unit tests for version resolver and bucketing logic (AC: #2, #3)
- [ ] Task 10: Integration test: verify rollout percentage affects correct tenant set (AC: #2)

**Estimate:** 1.5-2 weeks

---

## 12. Implementation Sequence & Dependencies

```
Story 6.5a (Agent Registry)
    ├── Story 6.5b (Per-Tenant Customization)    [depends on 6.5a]
    ├── Story 6.5c (Isolation & Circuit Breakers) [depends on 6.5a]
    └── Story 6.5d (Versioning & Rollout)         [depends on 6.5a]
```

**Recommended sequence:**

| Week | Story | Notes |
|------|-------|-------|
| 1-2 | **6.5a** Agent Registry | Foundation — all other stories depend on this |
| 3 | **6.5c** Isolation & Circuit Breakers | Can start immediately after 6.5a (no 6.5b dependency) |
| 3-4 | **6.5b** Per-Tenant Customization | Can start in parallel with 6.5c (backend week 3, frontend week 4) |
| 5 | **6.5d** Versioning & Rollout | Depends on 6.5a only, but benefits from 6.5b's config resolution |
| 6 | Integration testing + polish | End-to-end validation of all four capabilities together |

**Stories 6.5b and 6.5c can run in parallel** (different engineers) after 6.5a is complete.

---

## 13. Effort Estimates

| Story | Backend | Frontend | Testing | Total |
|-------|---------|----------|---------|-------|
| 6.5a: Agent Registry | 1.5 weeks | 0.5 week (admin UI) | 0.5 week | **2.5 weeks** |
| 6.5b: Per-Tenant Config | 1 week | 1 week | 0.5 week | **2.5 weeks** |
| 6.5c: Isolation | 1 week | 0.5 week (dashboard) | 0.5 week | **2 weeks** |
| 6.5d: Versioning | 1 week | 0.5 week (admin UI) | 0.5 week | **2 weeks** |
| Integration + Polish | — | — | 1 week | **1 week** |

**Total: 6-7 weeks** (with parallelism: **5-6 weeks** using 2 engineers)

**Team Composition:**
- 1 senior backend engineer (all 4 stories)
- 1 frontend engineer (admin UI across stories 6.5a, 6.5b, 6.5d)
- 1 DevOps/SRE (Grafana dashboards, alert rules in 6.5c)

---

## 14. Risk Assessment

| # | Risk | Probability | Impact | Mitigation |
|---|------|------------|--------|------------|
| R1 | Registry adds latency to every agent call | Medium | Medium | Redis caching (1h TTL). Fallback: in-memory cache with 5-min refresh. Measured overhead target: <10ms. |
| R2 | Per-tenant prompt customization degrades agent quality | Medium | High | `append` mode as default (safe). `replace` mode requires admin acknowledgment. Quality monitoring per tenant via execution log. |
| R3 | Circuit breaker false-positives (opens when agent is healthy) | Low | Medium | Conservative thresholds (5 failures in 120s). Manual reset API. Alert on state changes for human verification. |
| R4 | Version rollout causes inconsistent behavior across tenants | Low | Medium | Deterministic bucketing (same tenant = same version). Execution log tracks version for debugging. |
| R5 | Migration complexity for existing 7 agents | Low | Low | Seed data migration is idempotent. Orchestrator modification is backward-compatible. Feature flag for gradual cutover. |

---

## 15. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Agent registration time** | <5 minutes (via API/UI) | Time from definition to discoverable |
| **Custom agent lead time** | <4 weeks (down from 5-9) | Design → production for medium-complexity agent |
| **Per-tenant customization** | 100% of enterprise tenants can customize | Adoption rate tracked via `tenant_agent_configs` |
| **Circuit breaker false positive rate** | <1% | Manual resets / total circuit opens |
| **Version rollout safety** | 0 tenant-impacting regressions from rollouts | Rollback events / total version rollouts |
| **Registry latency overhead** | <10ms P99 | Prometheus: `agent_registry_resolve_duration_seconds` |
| **Zero regression** | Existing 7 agents function identically after migration | Full integration test suite passes |

---

## Appendix: Relationship to Existing Stories

| Existing Story | Relationship | Action |
|---|---|---|
| **Story 6.5: Agent SDK & Marketplace** | Stories 6.5a-d are **prerequisites** for 6.5 | 6.5a-d provide the registry and customization that the SDK and Marketplace build upon. Original Story 6.5 (SDK, marketplace, security scan, ratings) remains but now depends on 6.5a completion. |
| **Story 7.x: Agent Skills** | Agent Skills (Epic 7) **builds on** the registry | Skill Registry Service (Epic 7) can extend `agent_definitions` with skill metadata rather than maintaining a separate registry. Reduces architectural duplication. |
| **Story 2.8: Agent Execution Engine** | Execution guard **enhances** existing engine | Circuit breakers and token guards integrate into the existing execution flow without modifying the agent execution interface. |

---

**Document Status:** APPROVED
**Author:** Winston (Architect Agent)
**PM Review:** John (PM Agent) — 2026-02-15
**Architecture Board Approval:** Winston (Architect Agent) — 2026-02-15
**Next Step:** Sprint planning (SM to incorporate Stories 6.9-6.12 when Epic 6 Phase 3 begins)
**Date:** 2026-02-15

### PM Review Log (2026-02-15)

| # | Finding | Type | Status |
|---|---------|------|--------|
| F1 | Target personas unclear — who registers agents? | Must-Fix | ✅ Fixed — Added "Target User Personas" section after Executive Summary |
| F2 | Prompt replace mode needs guardrails | Must-Fix | ✅ Fixed — Added AC8 (tier restriction) + AC9 (validation) to Story 6.5b |
| F3 | Execution log retention undefined | Must-Fix | ✅ Fixed — Added 1yr hot + 7yr cold retention to Story 6.5a AC1 |
| F4 | Story numbering convention (6.5a→6.9) | Advisory | ✅ Applied in epic update |
| F5 | Execution guard needs feature flag for canary rollout | Advisory | Noted — DEV to implement during Story 6.11 |
| F6 | Circuit breaker should tag tenant-specific prompt failures | Advisory | Noted — DEV to consider during Story 6.11 |
| F7 | Lead time metric needs tracking columns | Advisory | Noted — Add `first_execution_at` to `agent_definitions` during Story 6.9 |

**PM Verdict:** Approved with findings applied. Ready for Architecture Board.

### Architecture Board Sign-Off (2026-02-15)

**APPROVED.** I've reviewed John's 3 must-fix amendments and confirm they are architecturally sound:

| PM Finding | Architect Assessment |
|---|---|
| F1: Target Personas | Correct scoping. Phase 1 = internal + tenant admins. SDK users in Phase 2 (Story 6.5). Prevents scope creep. |
| F2: Prompt Replace Guardrails | AC8 (Enterprise tier gating) and AC9 (injection pattern detection) are necessary safeguards. The prompt validation regex should be maintained as a configurable blocklist, not hardcoded — DEV to note during implementation. |
| F3: Execution Log Retention | 1yr hot + 7yr cold aligned with SOC 2 (Story 6.7) is correct. The S3/Blob archive strategy should use the same archival pipeline as the main audit trail to avoid maintaining two cold storage systems. |

John's advisory findings (F4-F7) are also reasonable. Story renumbering to 6.9-6.12 maintains convention. Feature flag for execution guard canary (F5) is standard practice. Circuit breaker tenant-prompt tagging (F6) is a good edge case catch.

**Epic structure update verified.** Phase 3 expansion from 3 to 5 weeks is justified. The dependency chain (6.9 → 6.10/6.11 parallel → 6.12 → 6.5) is correct.

**Signed:** Winston, Architecture Lead
**Date:** 2026-02-15
