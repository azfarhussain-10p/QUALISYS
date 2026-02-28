"""
QUALISYS — BA Consultant Agent
Story: 2-7-agent-pipeline-orchestration

AC-17f: Builds system prompt + context, calls call_llm(), returns AgentResult.
Artifact: requirements_matrix (JSON content_type).
"""

from __future__ import annotations

from typing import Optional

from src.patterns.llm_pattern import LLMResult, call_llm

# AC-17g: artifact metadata
ARTIFACT_TYPE = "requirements_matrix"
CONTENT_TYPE  = "json"
TITLE         = "Requirements Coverage Matrix"

# Budget per Story 2-7 constraint C10 — formal tier enforcement deferred to Story 2-8
_DAILY_BUDGET = 100_000

SYSTEM_PROMPT = """\
You are a Business Analyst specialising in software quality assurance.
Analyse the provided project artefacts (documents, GitHub source, and DOM crawl data)
and produce a Requirements Coverage Matrix in valid JSON.

The JSON must be an array of objects with these fields:
  - requirement_id   (string, e.g. "REQ-001")
  - description      (string, concise requirement summary)
  - source           (string, where found: "document" | "github" | "crawl")
  - coverage_status  ("covered" | "partially_covered" | "not_covered")
  - notes            (string, any gaps or risks observed)

Respond ONLY with valid JSON — no markdown fences, no preamble.
"""


class BAConsultantAgent:
    """
    Business Analyst Consultant — produces a requirements coverage matrix from project context.
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
            LLMResult with JSON content for the requirements matrix.
        """
        prompt = _build_prompt(context)
        return await call_llm(
            prompt=prompt,
            tenant_id=tenant_id,
            daily_budget=_DAILY_BUDGET,
            agent_type="ba_consultant",
            system_prompt=SYSTEM_PROMPT,
            context_hash=context_hash,
        )


def _build_prompt(context: dict) -> str:
    parts: list[str] = []

    if context.get("doc_text"):
        parts.append(f"## Uploaded Documents\n\n{context['doc_text']}")

    if context.get("github_summary"):
        parts.append(f"## GitHub Repository Analysis\n\n{context['github_summary']}")

    if context.get("crawl_data"):
        parts.append(f"## DOM Crawl Data\n\n{context['crawl_data']}")

    if not parts:
        parts.append("No project data available. Return an empty JSON array [].")

    return "\n\n---\n\n".join(parts)
