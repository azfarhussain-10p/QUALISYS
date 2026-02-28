"""
QUALISYS — Automation Consultant Agent
Story: 2-7-agent-pipeline-orchestration

AC-17f: Builds system prompt + context, calls call_llm(), returns AgentResult.
Artifact: playwright_scripts (TypeScript content_type).
"""

from __future__ import annotations

from typing import Optional

from src.patterns.llm_pattern import LLMResult, call_llm

# AC-17g: artifact metadata
ARTIFACT_TYPE = "playwright_scripts"
CONTENT_TYPE  = "typescript"
TITLE         = "Playwright Test Scripts"

_DAILY_BUDGET = 100_000

SYSTEM_PROMPT = """\
You are a Senior Test Automation Engineer specialising in Playwright with TypeScript.
Using the DOM crawl data, manual test checklists, and project artefacts provided,
generate syntactically valid Playwright TypeScript test scripts.

Requirements:
  - Use @playwright/test with TypeScript
  - Each test file must import { test, expect } from '@playwright/test'
  - Organise tests in test.describe() blocks by feature or user flow
  - Use page.goto(), page.locator(), page.fill(), expect(locator) assertions
  - Include beforeEach / afterEach hooks where appropriate
  - Use page.waitForLoadState() and avoid hard waits (no page.waitForTimeout())
  - Scripts must be syntactically valid TypeScript — no pseudocode or placeholders

Respond ONLY with TypeScript code — one or more test files separated by
// --- FILE: <filename>.spec.ts --- comments. No markdown fences.
"""


class AutomationConsultantAgent:
    """
    Automation Consultant — produces Playwright TypeScript test scripts.
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
            LLMResult with TypeScript content for the Playwright scripts.
        """
        prompt = _build_prompt(context)
        return await call_llm(
            prompt=prompt,
            tenant_id=tenant_id,
            daily_budget=_DAILY_BUDGET,
            agent_type="automation_consultant",
            system_prompt=SYSTEM_PROMPT,
            context_hash=context_hash,
        )


def _build_prompt(context: dict) -> str:
    parts: list[str] = []

    if context.get("crawl_data"):
        parts.append(f"## DOM Crawl Data (Selectors & Structure)\n\n{context['crawl_data']}")

    if context.get("doc_text"):
        parts.append(f"## Project Documents\n\n{context['doc_text']}")

    if context.get("github_summary"):
        parts.append(f"## GitHub Source Analysis\n\n{context['github_summary']}")

    if not parts:
        parts.append("No project data available. Return a minimal Playwright test template.")

    return "\n\n---\n\n".join(parts)
