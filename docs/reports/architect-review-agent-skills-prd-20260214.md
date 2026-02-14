# Architect Review: Agent Skills Integration PRD

**Document:** `docs/planning/prd-agent-skills-integration.md`
**PM Validation Report:** `docs/planning/validation-report-2026-02-14-agent-skills-prd.md`
**Architecture Checklist:** `.bmad/bmm/workflows/3-solutioning/architecture/checklist.md`
**Date:** 2026-02-14
**Reviewer:** Winston (Architect Agent)

---

## Part 1: Review of PM Validation Report

### PM Findings Assessment

The PM's validation report scored 48/56 (86%) and identified 3 critical items and 4 partial items. My assessment of the PM's findings:

#### PM Findings I Agree With

✓ **F1: FRs contain implementation details** — Correct. FR-SK8, FR-SK15, FR-SK26 cross into HOW territory. The PM's suggested rewording is appropriate.

✓ **F3: Stories lack size estimates** — **RESOLVED.** The PM validated against the document before Section 18 included the Story Size Estimates table (lines 1349-1373). The final document now has T-shirt sizing and story points for all 20 stories totaling 102 SP. This finding is no longer applicable.

✓ **P1: Vertical slicing concern** — Stories 7.14 (Observability) and 7.15 (Regression Tests) are indeed horizontal. However, for infrastructure concerns like observability, horizontal stories are pragmatically acceptable. The PM's suggestion to embed observability into integration stories would create 6 stories that each partially implement monitoring — harder to validate than one dedicated story. **My recommendation: Keep as-is. Horizontal infrastructure stories are appropriate here.**

✓ **P2: Story 7.11 sizing** — Agreed. Story 7.11 (BAConsultant Full Integration: 3 skills + chaining + validation) is sized L/8 SP, which is at the upper bound but acceptable for a 4-hour AI agent session given the skills infrastructure already exists from Phase 1-2. Story 7.20 (Documentation: 6 updates) at M/5 SP is reasonable.

#### PM Findings I Disagree With

✗ **F2: Missing consolidated References section** — **RESOLVED.** The final document includes a References section at lines 49-62 with 8 reference documents (R1-R8) in a structured table, plus an explicit terminology divergence note. The PM appears to have validated against an earlier draft.

✗ **P3: Naming consistency** — The PRD explicitly addresses this at line 62: "This PRD intentionally reclassifies the 'Skill Adapter Layer' (evaluation docs) as 'Skill Adapter Library'..." This is intentional divergence with documented rationale, not an oversight.

#### PM Findings Missing from Report

The PM's validation focused on PRD completeness. As expected, it did not deeply assess architectural soundness. The following architectural concerns were not covered:

1. **Claude API beta dependency risk** — FR-SK8 and Story 7.3 AC2 rely on Claude API `container` parameter which is in beta. The PRD notes this in constraints (line 1476) but doesn't address what happens if the beta is discontinued or significantly changed.

2. **Skill Registry as tenant-scoped vs global** — Skills are stored in per-tenant schemas (line 922: "within each tenant schema"), but skills are platform capabilities, not tenant data. If every tenant has identical skills, this creates N copies of identical data across N tenant schemas. Decision D7 (line 1555) says "consistent with existing multi-tenant pattern" — but skills are fundamentally different from user data.

3. **Network policy egress gap** — The network policy at line 880 allows egress to `0.0.0.0/0` on port 443 (commented as "Claude API"), which is overly permissive. Should be restricted to Anthropic IP ranges.

---

## Part 2: Architecture Validation of PRD

**Note:** This is a feature-extension PRD, not an architecture document. The architecture checklist is designed for architecture docs. I'm applying it contextually — assessing whether the PRD's architectural design sections (7-17) provide sufficient guidance for the architecture update (Story 7.20 AC1).

### 1. Decision Completeness
**Pass Rate: 7/9 (78%)**

| Mark | Item | Evidence |
|---|---|---|
| ✓ PASS | Critical decisions resolved | Decision Log (Section 25): 10 decisions documented. All major choices made: Epic timing (D1), MCP deferral (D2), POC parallel (D3), hybrid approach (D4), abstraction layer (D5), fallback guarantee (D6), tenant schema (D7), skill count (D8), feature flags (D9), A/B deferral (D10). |
| ✓ PASS | Important categories addressed | Skill execution, governance, observability, security, CI/CD, database schema, versioning, vendor lock-in — all covered. |
| ✓ PASS | No placeholder text | Full scan — no TBD, TODO, or placeholder markers found. |
| ✓ PASS | Deferred items have rationale | MCP Bridge deferred to Epic 8 with detailed rationale (Section 4.3). A/B testing deferred with explanation (D10). Multi-LLM deferred with abstraction plan (Section 23). |
| ✓ PASS | Data persistence decided | PostgreSQL skills tables in tenant schemas (Section 15), Redis caching for metadata (Story 7.6 AC6). |
| ✓ PASS | API pattern chosen | REST APIs for Skill Registry and Proxy (Sections 7.2, Story 7.1 AC3, Story 7.3 AC3). Consistent with main architecture. |
| ⚠ PARTIAL | Auth/authz strategy defined | RBAC extensions defined (Section 14.1). However, service-to-service authentication between Orchestrator → Skill Registry → Skill Proxy is underspecified. Line 846 mentions "Service-to-service tokens" but no detail on mechanism (mTLS, JWT, API keys?). |
| ✓ PASS | Deployment target selected | Kubernetes, consistent with main architecture. Pod specs provided (Section 14.3). HPA configured (Story 7.7). |
| ⚠ PARTIAL | All FRs have architectural support | All 28 FRs mapped to stories with ACs. However, FR-SK23 (skill execution approval exemptions for pre-approved combinations) is P2 and has no implementation detail — no story AC addresses exemption caching or matching logic. |

### 2. Version Specificity
**Pass Rate: 2/4 (50%)**

| Mark | Item | Evidence |
|---|---|---|
| ✗ FAIL | Technology versions specified | No version numbers for new components. Skill Registry and Skill Proxy are new FastAPI services but no Python, FastAPI, or dependency versions specified. Claude API version/model not specified. The PRD relies on main architecture versions but should explicitly state which versions the new services will use. |
| ➖ N/A | Versions verified via WebSearch | Feature PRD — defers to main architecture verification log. Acceptable. |
| ✓ PASS | Compatible versions | All new components use existing stack (FastAPI, PostgreSQL, Redis, Kubernetes) — inherently compatible. |
| ✓ PASS | Breaking changes noted | Claude API beta headers dependency noted as constraint (line 1476). |

### 3. Starter Template Integration
**N/A** — No starter template applicable.

### 4. Novel Pattern Design
**Pass Rate: 11/13 (85%)**

#### Pattern Detection

| Mark | Item | Evidence |
|---|---|---|
| ✓ PASS | Novel concepts identified | Progressive Disclosure Model (3-level skill loading), Skill-Aware RAG Pre-Fetching, Zero Regression Fallback Architecture, Feature Flag Gradual Rollout — all unique patterns documented. |
| ✓ PASS | Non-standard patterns documented | Progressive disclosure (metadata → instructions → resources) is a novel loading strategy. Skill-aware RAG tag filtering is new. Both well-documented with code examples. |
| ✓ PASS | Multi-epic workflows captured | Agent chain compatibility (Section 9.4) addresses cross-epic workflow. Skills POC running parallel with Epic 6 documented in roadmap. |

#### Pattern Documentation Quality

| Mark | Item | Evidence |
|---|---|---|
| ✓ PASS | Pattern name and purpose defined | Each pattern has clear purpose: Progressive Disclosure (token reduction), Fallback Architecture (zero regression), Skill-Aware RAG (relevance improvement). |
| ✓ PASS | Component interactions specified | Section 7.1 system architecture diagram shows all component relationships. Section 7.2 request flow shows 12-step invocation sequence. |
| ✓ PASS | Data flow documented | Request flow (Section 7.2) is a 12-step sequence diagram. Fallback flow (Section 7.3) covers all failure modes. |
| ✓ PASS | Implementation guide provided | Code examples in Sections 9-12, 17, 23. SQL schemas in Section 15. K8s configs in Sections 14.3-14.4. CI/CD pipeline in Section 13. |
| ✓ PASS | Edge cases and failure modes | Fallback architecture (Section 7.3) covers: registry unavailable, proxy timeout, Claude API error, governance blocks. Each has defined behavior. |
| ⚠ PARTIAL | States and transitions defined | Skill lifecycle states clear (Draft → Active → Deprecated → Retired, Section 16.2). Skill execution states clear (success, error, timeout, fallback). **Missing:** Skill approval states transition diagram — what happens if approval times out? What's the SLA for approval turnaround? |

#### Pattern Implementability

| Mark | Item | Evidence |
|---|---|---|
| ✓ PASS | Implementable by AI agents | Code examples are concrete and copy-paste ready. Class signatures, method bodies, SQL DDL all provided. |
| ⚠ PARTIAL | No ambiguous decisions | Most decisions clear. **Ambiguity:** The `_select_skills` method (Section 9.3, line 557) calls `self._context_matches_skill(skill, context)` but the matching logic is not defined. What attributes of ProjectContext match which skill tags? This is a critical algorithm left unspecified. |
| ✓ PASS | Clear component boundaries | Skill Registry (metadata), Skill Proxy (execution), Skill Adapter (translation), Governance (approval) — clear responsibilities, no overlap. |

### 5. Implementation Patterns
**Pass Rate: 9/12 (75%)**

#### Pattern Categories Coverage

| Mark | Item | Evidence |
|---|---|---|
| ✓ PASS | Naming Patterns | API routes follow main architecture: `/api/v1/skills`, `/api/v1/skills/{skill_id}/execute`. DB tables: `skills`, `skill_executions`, `skill_approvals` — consistent snake_case. |
| ✓ PASS | Structure Patterns | Skill directory structure (Section 13.2): `skills/{agent}/{skill-name}/SKILL.md + scripts/ + resources/ + tests/`. Clear and consistent. |
| ✓ PASS | Format Patterns | Inherits main architecture API response format. Skill execution audit logging format defined (line 228). |
| ✓ PASS | Communication Patterns | Service-to-service REST calls. Redis caching for metadata. Prometheus metrics for observability. |
| ✓ PASS | Lifecycle Patterns | Retry logic (3x exponential backoff), fallback to full-context, circuit breaker implied via feature flags. Skill lifecycle (Draft → Active → Deprecated → Retired). |
| ✓ PASS | Location Patterns | `/api/v1/skills/...` URL structure. Skill files at `skills/{agent}/{name}/`. Config in skill metadata. |
| ✓ PASS | Consistency Patterns | Structured logging via OpenTelemetry (Section 17.1). Prometheus metrics naming convention (Section 17.3). |

#### Pattern Quality

| Mark | Item | Evidence |
|---|---|---|
| ✓ PASS | Concrete examples | Code examples for: SkillAwareAgentOrchestrator, SkillAwareRAG, SkillGovernance, SkillProxyService, SkillProvider abstraction. SQL DDL. K8s YAML. GitHub Actions YAML. |
| ✓ PASS | Conventions unambiguous | Naming, structure, and API patterns are explicit. No interpretation required. |
| ⚠ PARTIAL | Patterns cover all technologies | Strong coverage for Python backend, PostgreSQL, Kubernetes, CI/CD. **Gap:** No frontend patterns for the updated approval dashboard UI (FR-SK22, Story 7.8 AC4). How does the React frontend discover and display skill approvals? |
| ✗ FAIL | No gaps where agents would guess | **Gap 1:** Skill selection algorithm (`_context_matches_skill`) undefined — agents must invent matching logic. **Gap 2:** Redis cache key structure for skill metadata not specified. **Gap 3:** How does the Skill Proxy authenticate to Claude API? Direct API key? Per-tenant key? Shared key? **Gap 4:** SKILL.md file format not fully specified — only references "Anthropic SKILL.md specification" without defining the schema QUALISYS expects. |
| ✓ PASS | Patterns don't conflict | All patterns consistent with main architecture. No contradictions. |

### 6. Technology Compatibility
**Pass Rate: 7/8 (88%)**

| Mark | Item | Evidence |
|---|---|---|
| ✓ PASS | Stack coherence | All new components use existing stack: FastAPI, PostgreSQL, Redis, Kubernetes. No new technology introduced. |
| ✓ PASS | API patterns consistent | REST throughout. No mixing of patterns. |
| ✓ PASS | Auth compatible | RBAC extensions (Section 14.1) build on existing role system. |
| ✓ PASS | Third-party services compatible | Claude API is HTTP-based, compatible with FastAPI async HTTP clients. |
| ✓ PASS | Deployment target supports all | Kubernetes supports all new services. Pod specs and network policies provided. |
| ✓ PASS | Background job system compatible | Inherits BullMQ/Redis. Skill execution queuing consistent with existing patterns. |
| ⚠ PARTIAL | Real-time compatible | Skill execution telemetry uses Prometheus/Grafana (compatible). However, the PRD doesn't address whether skill execution progress should emit SSE events to the frontend (e.g., "Skill executing... 3/5 complete"). The main architecture uses SSE for test execution updates — should skills follow the same pattern? |
| ✓ PASS | Storage compatible | PostgreSQL tenant schemas, Redis caching — consistent with existing data layer. |

### 7. Document Structure
**Pass Rate: 4/5 (80%)**

| Mark | Item | Evidence |
|---|---|---|
| ✓ PASS | Executive summary | Section 1 (lines 66-94): Clear problem, solution, and strategic decision. |
| ⚠ PARTIAL | Decision summary table | Decision Log (Section 25) has 10 decisions with rationale and dates. **Missing columns:** Version numbers, Affects Epics, and Priority are absent. Format is simpler than main architecture's Decision Summary table. |
| ✓ PASS | Project structure | Skill directory structure (Section 13.2) shows complete tree for skills/. New service locations clear from architecture diagram. |
| ✓ PASS | Implementation patterns comprehensive | Sections 9-17 provide extensive implementation guidance. |
| ✓ PASS | Novel patterns documented | Progressive Disclosure, Fallback Architecture, Skill-Aware RAG all documented with code examples. |

### 8. AI Agent Clarity
**Pass Rate: 8/12 (67%)**

| Mark | Item | Evidence |
|---|---|---|
| ✓ PASS | No ambiguous decisions | Major decisions clear. Minor ambiguity on skill selection logic (noted above). |
| ✓ PASS | Clear component boundaries | Registry, Proxy, Adapter, Governance — each with dedicated section. |
| ✓ PASS | File organization explicit | Skill directory structure defined. Service module locations implied from main architecture. |
| ✓ PASS | Common operations defined | CRUD for skills (Section 5.1), execution flow (Section 7.2), governance flow (Section 12.3). |
| ✓ PASS | Novel patterns have guidance | Code examples for all novel patterns. |
| ✓ PASS | Clear constraints | 8 skills max per request, 120s timeout, 50 req/s Claude API limit, tenant resource limits. |
| ✓ PASS | No conflicting guidance | Consistent throughout. |
| ⚠ PARTIAL | Sufficient detail for implementation | Most areas yes. **Gaps:** Skill selection algorithm, Redis cache keys, SKILL.md schema, frontend approval UI. |
| ✓ PASS | File paths explicit | `skills/{agent}/{skill-name}/` structure clear. Service paths inherit from main architecture. |
| ✗ FAIL | Integration points clearly defined | **Critical gap:** The PRD describes the Skill Adapter Library as translating LangChain ↔ Claude API formats, but the actual translation mapping is not defined. What fields from `ProjectContext` map to what Claude API parameters? The `translate()` and `translate_response()` methods have signatures but no mapping specification. An agent implementing Story 7.4 will need to reverse-engineer the Claude API and LangChain context structures. |
| ⚠ PARTIAL | Error handling patterns | Fallback architecture covers service-level errors. **Missing:** What error codes does the Skill Registry return? What error codes does the Skill Proxy return? No HTTP error response catalog for the new services. |
| ⚠ PARTIAL | Testing patterns | Regression test suite described (Story 7.15). Unit test coverage targets defined (>90%). **Missing:** No sample test code. No integration test patterns for skill execution. No guidance on how to mock Claude API in tests. |

### 9. Practical Considerations
**Pass Rate: 8/10 (80%)**

| Mark | Item | Evidence |
|---|---|---|
| ✓ PASS | Stack has good documentation | All existing stack components. Claude API documentation referenced. |
| ✓ PASS | Dev environment setup | New services use existing infrastructure patterns. Podman compose extension needed but straightforward. |
| ⚠ PARTIAL | No experimental technologies on critical path | Claude API Skills (`container` parameter) is in beta (line 1476). This is on the critical path for the entire Epic 7. If Anthropic changes the API, significant rework required. The `SkillProvider` abstraction mitigates but doesn't eliminate risk. |
| ✓ PASS | Deployment target supports all | Kubernetes supports new services. Pod specs provided. |
| ✓ PASS | Can handle expected load | NFR-SK4: 500 req/s for Registry. NFR-SK5: 100 concurrent executions for Proxy. NFR-SK8: 50,000+ invocations/day. Scaling via HPA documented. |
| ✓ PASS | Data model supports growth | Indexes on skill_executions (tenant_id, skill_id, created_at). Audit retention policy (90 days configurable). |
| ✓ PASS | Caching strategy defined | Redis 24h TTL for skill metadata (Story 7.6 AC6). |
| ✓ PASS | Background processing defined | Skill execution is synchronous (request-response via Proxy) but fallback handling is async. Integration with existing BullMQ for governance notifications. |
| ✓ PASS | Novel patterns scalable | Progressive disclosure reduces token load linearly. Skill Registry stateless (HPA scales). Proxy stateless (HPA scales). |
| ⚠ PARTIAL | Architecture handles expected load | NFR targets well-defined. **Concern:** 100 concurrent skill executions (NFR-SK5) against Claude API rate limit of 50 req/s (constraint, line 1474) means at peak, half the requests will queue. The PRD notes "request quota increase" as mitigation but this is external dependency. Internal queuing strategy not defined. |

### 10. Common Issues
**Pass Rate: 9/9 (100%)**

| Mark | Item | Evidence |
|---|---|---|
| ✓ PASS | Not overengineered | Pragmatic: 2 new microservices + 1 library (not 3 microservices). MCP bridge deferred. A/B testing deferred. |
| ✓ PASS | Standard patterns used | REST APIs, Kubernetes, PostgreSQL, Redis, GitHub Actions — all standard. |
| ✓ PASS | Complexity justified | 21 skills justified by $136,800/year savings at 150 tenants. POC validates before investment. |
| ✓ PASS | Maintenance appropriate | +15% operational overhead documented and budgeted ($30K/year). |
| ✓ PASS | No anti-patterns | Clean separation of concerns. No god services. Stateless services. |
| ✓ PASS | Performance bottlenecks addressed | Caching (Redis), pre-warming (implied via HPA), connection pooling, timeout handling. |
| ✓ PASS | Security best practices | Pod security context (non-root, read-only fs), network policies, secrets management, audit trails. |
| ✓ PASS | Migration paths preserved | SkillProvider abstraction (Section 23) enables provider swap. SKILL.md files are LLM-agnostic. |
| ✓ PASS | Novel patterns follow principles | Progressive disclosure follows information architecture principles. Fallback follows graceful degradation principles. |

---

## Summary

### PM Validation Report Assessment

| PM Finding | Architect Assessment |
|---|---|
| F1: FRs contain implementation details | **Agree** — Fix FR-SK8, FR-SK15, FR-SK26 |
| F2: Missing References section | **Resolved** — References section exists at lines 49-62 |
| F3: Missing story estimates | **Resolved** — Story Size Estimates table at lines 1349-1373 |
| P1: Horizontal stories | **Disagree** — Keep observability as dedicated story |
| P2: Story 7.11 oversized | **Agree** — Monitor but acceptable at L/8 SP |
| P3: Naming inconsistency | **Resolved** — Intentional divergence documented at line 62 |
| P4: Code sample issue | **Agree** — Minor, fix `rag_service` in constructor |

**PM Report Accuracy: 4/7 findings still applicable.** 3 findings already resolved in final document.

### Architecture Validation Totals

| Section | Pass Rate |
|---|---|
| 1. Decision Completeness | 7/9 (78%) |
| 2. Version Specificity | 2/4 (50%) |
| 3. Starter Template | N/A |
| 4. Novel Pattern Design | 11/13 (85%) |
| 5. Implementation Patterns | 9/12 (75%) |
| 6. Technology Compatibility | 7/8 (88%) |
| 7. Document Structure | 4/5 (80%) |
| 8. AI Agent Clarity | 8/12 (67%) |
| 9. Practical Considerations | 8/10 (80%) |
| 10. Common Issues | 9/9 (100%) |
| **Overall** | **65/82 (79%)** |

### Critical Issues (3)

1. **Skill selection algorithm undefined** — `_context_matches_skill()` has no specification. What ProjectContext attributes match which skill tags? This is core routing logic that agents cannot invent correctly without guidance.

2. **Context translation mapping unspecified** — `SkillAdapter.translate()` and `translate_response()` have method signatures but no field mapping between LangChain `ProjectContext` and Claude API format. Agents implementing Story 7.4 need this.

3. **Claude API beta dependency on critical path** — The `container` parameter is in beta. No contingency plan if beta changes significantly or is deprecated before Epic 7 Phase 3.

### Important Issues (5)

4. **Service-to-service auth unspecified** — How do Orchestrator, Skill Registry, and Skill Proxy authenticate to each other? mTLS? JWT? API keys?

5. **Skill Registry tenant scoping questionable** — Skills are platform capabilities, not tenant data. Storing identical skill definitions in every tenant schema creates unnecessary duplication. Consider a shared `public.skills` table with tenant-specific `skill_configurations` for overrides.

6. **Network policy overly permissive** — Egress rule allows `0.0.0.0/0:443` instead of restricting to Anthropic IP ranges.

7. **New service version numbers missing** — No explicit Python/FastAPI/dependency versions for new Skill Registry and Skill Proxy services.

8. **Frontend approval UI patterns absent** — No React component or API integration patterns for the updated approval dashboard (FR-SK22, Story 7.8 AC4).

### Recommendations Before Architecture Board Review

#### Must Fix (3 items)

1. **Define skill selection algorithm** — Specify what `ProjectContext` attributes (document_type, agent_stage, task_type, project_domain) map to which skill tags. Provide a concrete example: "When context.document_type == 'pdf', select skills tagged 'document-parsing'."

2. **Define context translation mapping** — Specify the field mapping: `ProjectContext.tenant_id → system_prompt metadata`, `ProjectContext.query → user message`, `RAG results → tool_results`, etc. At minimum, show the Claude API request body structure produced by `translate()`.

3. **Add Claude API contingency plan** — What happens if `container` parameter is deprecated? Options: (a) Implement progressive disclosure via prompt engineering (stuff SKILL.md into system prompt), (b) Switch to function calling as execution mechanism. Document the pivot strategy with estimated effort.

#### Should Fix (3 items)

4. **Specify service-to-service auth** — Add to Section 14: "Service-to-service communication uses Kubernetes service account tokens with RBAC (or mTLS via service mesh)."

5. **Reconsider skills table placement** — Evaluate `public.skills` (shared) + `tenant_{id}.skill_configurations` (per-tenant overrides) vs current full tenant-schema approach. Document the trade-off decision.

6. **Tighten network policy** — Replace `0.0.0.0/0` with Anthropic API CIDR ranges, or use an egress proxy.

#### Consider (2 items)

7. **Add Claude API request/response example** — Show a complete curl command or Python request demonstrating the `container` parameter with a QUALISYS skill. This grounds the abstraction in reality.

8. **Add test mocking guidance** — How should agents mock Claude API in unit/integration tests? Recommend `httpx.MockTransport` or `responses` library with example.

---

## Architect Verdict

**Rating: ⚠ GOOD (79%) — Architecturally sound with targeted gaps to fill**

This is an impressive feature PRD with substantially more architectural depth than typical PRDs. The progressive disclosure model, fallback architecture, and vendor lock-in mitigation are well-designed. The security model (pod security, network policies, tenant isolation) is thorough.

The three critical gaps (skill selection logic, context translation mapping, API beta contingency) are the kind of specification detail that, if left unresolved, will cause implementation divergence — different agents will make different assumptions. These should be resolved before the Architecture Board review.

**After fixing 3 critical items: Ready for Architecture Board review.**

---

**Report saved to:** `docs/reports/architect-review-agent-skills-prd-20260214.md`
**Reviewer:** Winston (Architect Agent)
**Next Step:** Fix 3 critical items → Architecture Board review
