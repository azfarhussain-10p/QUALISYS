"""
QUALISYS — QA Consultant Agent
Story: 2-7-agent-pipeline-orchestration

AC-17f: Builds system prompt + context, calls call_llm(), returns AgentResult.
Artifact: test_checklists (Markdown content_type).
"""

from __future__ import annotations

from typing import Optional

from src.patterns.llm_pattern import LLMResult, call_llm

# AC-17g: artifact metadata
ARTIFACT_TYPE = "test_checklists"
CONTENT_TYPE  = "markdown"
TITLE         = "Manual Test Checklists"

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


class QAConsultantAgent:
    """
    QA Consultant — produces manual test checklists and BDD scenarios.
    AC-17f: async run(context, tenant_id) -> LLMResult via call_llm().
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
