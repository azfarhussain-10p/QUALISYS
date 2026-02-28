"""
QUALISYS — QA Consultant Agent
Story: 2-7-agent-pipeline-orchestration, 2-10-test-artifact-storage-viewer

AC-17f: Builds system prompt + context, calls call_llm(), returns AgentResult.
AC-25:  run_bdd() — secondary LLM call producing BDD/Gherkin scenario artifact.
Artifact: manual_checklist (text/markdown), bdd_scenario (text/plain).
"""

from __future__ import annotations

from typing import Optional

from src.patterns.llm_pattern import LLMResult, call_llm

# AC-17g: artifact metadata
ARTIFACT_TYPE = "manual_checklist"
CONTENT_TYPE  = "text/markdown"
TITLE         = "Manual Test Checklists"

BDD_ARTIFACT_TYPE = "bdd_scenario"
BDD_CONTENT_TYPE  = "text/plain"
BDD_TITLE         = "BDD/Gherkin Test Scenarios"

_DAILY_BUDGET = 100_000

SYSTEM_PROMPT = """\
You are a Senior QA Engineer specialising in manual test design.
Using the requirements, coverage gaps, and project artefacts provided,
produce comprehensive Manual Test Checklists in Markdown format.

Structure your output as follows:
  # Manual Test Checklists
  ## <Feature / Module Name>
  ### Test Scenario: <Scenario Title>
  **Given** <precondition>
  **When** <action>
  **Then** <expected outcome>
  - [ ] <specific check>
  - [ ] <specific check>

Include BDD/Gherkin scenarios for critical paths. Cover happy paths, edge cases,
and error scenarios. Group by feature or user flow.
Respond ONLY with Markdown — no JSON, no preamble.
"""


BDD_SYSTEM_PROMPT = """\
You are a Senior QA Engineer specialising in Behaviour-Driven Development (BDD).
Using the requirements, coverage gaps, and project artefacts provided,
produce BDD test scenarios in standard Gherkin syntax.

Structure your output as follows:
  Feature: <Feature Name>

    Scenario: <Scenario Title>
      Given <precondition>
      When <action>
      Then <expected outcome>

    Scenario: <Another Scenario>
      Given <precondition>
      And <additional precondition>
      When <action>
      Then <expected outcome>
      And <additional assertion>

Cover happy paths, edge cases, and error scenarios. Group by Feature.
Respond ONLY with plain-text Gherkin — no Markdown fences, no JSON, no preamble.
"""


class QAConsultantAgent:
    """
    QA Consultant — produces manual test checklists and BDD scenarios.
    AC-17f: async run(context, tenant_id) -> LLMResult via call_llm().
    AC-25:  async run_bdd(context, tenant_id) -> LLMResult (Gherkin).
    """

    async def run(
        self, context: dict, tenant_id: str, *, context_hash: Optional[str] = None
    ) -> LLMResult:
        """
        Build prompt from assembled context and call the LLM.

        Args:
            context:      {"doc_text": str, "github_summary": str, "crawl_data": str}
            tenant_id:    Tenant UUID string for budget tracking.
            context_hash: SHA-256 of assembled context dict (AC-18); None → fallback in call_llm.

        Returns:
            LLMResult with Markdown content for the test checklists.
        """
        prompt = _build_prompt(context)
        return await call_llm(
            prompt=prompt,
            tenant_id=tenant_id,
            daily_budget=_DAILY_BUDGET,
            agent_type="qa_consultant",
            system_prompt=SYSTEM_PROMPT,
            context_hash=context_hash,
        )

    async def run_bdd(
        self, context: dict, tenant_id: str, *, context_hash: Optional[str] = None
    ) -> LLMResult:
        """
        AC-25: Secondary LLM call producing BDD/Gherkin scenarios.

        Uses a separate agent_type ("qa_consultant_bdd") for cache key isolation
        so the BDD result is never confused with the primary manual_checklist result.
        """
        prompt = _build_prompt(context)
        return await call_llm(
            prompt=prompt,
            tenant_id=tenant_id,
            daily_budget=_DAILY_BUDGET,
            agent_type="qa_consultant_bdd",
            system_prompt=BDD_SYSTEM_PROMPT,
            context_hash=context_hash,
        )


def _build_prompt(context: dict) -> str:
    parts: list[str] = []

    if context.get("doc_text"):
        parts.append(f"## Project Documents\n\n{context['doc_text']}")

    if context.get("github_summary"):
        parts.append(f"## GitHub Source Analysis\n\n{context['github_summary']}")

    if context.get("crawl_data"):
        parts.append(f"## DOM Crawl Data\n\n{context['crawl_data']}")

    if not parts:
        parts.append("No project data available. Return a minimal checklist template.")

    return "\n\n---\n\n".join(parts)
