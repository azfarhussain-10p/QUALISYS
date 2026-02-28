"""
QUALISYS — Agent Run Service
Story: 2-6-ai-agent-selection-ui

AC-15: AGENT_DEFINITIONS — hardcoded list of 3 MVP agents (BAConsultant, QAConsultant, AutomationConsultant)
AC-16: create_run() — INSERT agent_runs + agent_run_steps rows, status='queued'

Security (C1): All SQL via text() with :params — no user data in f-string interpolation.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger


# ---------------------------------------------------------------------------
# Agent catalog — AC-15 (static definitions, no DB lookup)
# ---------------------------------------------------------------------------

VALID_AGENT_TYPES = {"ba_consultant", "qa_consultant", "automation_consultant"}

AGENT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "agent_type":       "ba_consultant",
        "name":             "BA Consultant",
        "description":      (
            "Analyses uploaded documents, GitHub source, and crawled pages to produce a "
            "requirements coverage matrix identifying tested and untested scenarios."
        ),
        "icon":             "ClipboardList",
        "required_inputs":  ["Documents", "GitHub repository (optional)", "DOM crawl data (optional)"],
        "expected_outputs": ["Requirements Coverage Matrix"],
    },
    {
        "agent_type":       "qa_consultant",
        "name":             "QA Consultant",
        "description":      (
            "Converts requirements and coverage gaps into manual test checklists and "
            "BDD/Gherkin scenarios ready for QA engineers."
        ),
        "icon":             "CheckSquare",
        "required_inputs":  ["Documents", "Requirements Coverage Matrix (from BA Consultant)"],
        "expected_outputs": ["Manual Test Checklists", "BDD/Gherkin Scenarios"],
    },
    {
        "agent_type":       "automation_consultant",
        "name":             "Automation Consultant",
        "description":      (
            "Generates syntactically valid Playwright TypeScript test scripts from DOM "
            "structure, crawl data, and QA checklists."
        ),
        "icon":             "Code2",
        "required_inputs":  ["DOM crawl data", "Manual Test Checklists (from QA Consultant)"],
        "expected_outputs": ["Playwright TypeScript Scripts"],
    },
]


# ---------------------------------------------------------------------------
# AgentRunService
# ---------------------------------------------------------------------------

class AgentRunService:
    """Manages agent_runs and agent_run_steps rows for pipeline execution tracking."""

    def list_agents(self) -> list[dict[str, Any]]:
        """Return the hardcoded list of 3 MVP agent definitions (no DB required)."""
        return AGENT_DEFINITIONS

    async def create_run(
        self,
        db:              AsyncSession,
        schema_name:     str,
        project_id:      str,
        user_id:         str,
        agents_selected: list[str],
        pipeline_mode:   str = "sequential",
    ) -> dict[str, Any]:
        """
        Insert an agent_run row (status='queued') and one agent_run_steps row per
        selected agent. Returns the new run as a dict.

        Raises 400 NO_AGENTS_SELECTED if the list is empty.
        Raises 400 INVALID_AGENT_TYPE if any type is not in VALID_AGENT_TYPES.
        """
        # AC-16: validate selection
        if not agents_selected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error":   "NO_AGENTS_SELECTED",
                    "message": "At least one agent must be selected.",
                },
            )

        invalid = [a for a in agents_selected if a not in VALID_AGENT_TYPES]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error":   "INVALID_AGENT_TYPE",
                    "message": f"Unknown agent type(s): {', '.join(invalid)}. "
                               f"Valid types: {', '.join(sorted(VALID_AGENT_TYPES))}.",
                },
            )

        run_id = str(uuid.uuid4())
        now    = datetime.now(timezone.utc)

        # INSERT agent_runs
        await db.execute(
            text(
                f'INSERT INTO "{schema_name}".agent_runs '
                f"(id, project_id, pipeline_mode, agents_selected, status, created_by, created_at) "
                f"VALUES (:id, :pid, :mode, CAST(:agents AS jsonb), 'queued', :uid, :now)"
            ),
            {
                "id":     run_id,
                "pid":    project_id,
                "mode":   pipeline_mode,
                "agents": json.dumps(agents_selected),
                "uid":    user_id,
                "now":    now,
            },
        )

        # INSERT one agent_run_steps row per selected agent
        for agent_type in agents_selected:
            step_id = str(uuid.uuid4())
            await db.execute(
                text(
                    f'INSERT INTO "{schema_name}".agent_run_steps '
                    f"(id, run_id, agent_type, status) "
                    f"VALUES (:id, :run_id, :agent_type, 'queued')"
                ),
                {"id": step_id, "run_id": run_id, "agent_type": agent_type},
            )

        await db.commit()

        logger.info(
            "agent_run: created",
            run_id=run_id,
            project_id=project_id,
            agents=agents_selected,
            pipeline_mode=pipeline_mode,
        )
        return {
            "id":              run_id,
            "project_id":      project_id,
            "pipeline_mode":   pipeline_mode,
            "agents_selected": agents_selected,
            "status":          "queued",
            "total_tokens":    0,
            "total_cost_usd":  0.0,
            "started_at":      None,
            "completed_at":    None,
            "error_message":   None,
            "created_at":      now,
        }

    async def get_run(
        self,
        db:          AsyncSession,
        schema_name: str,
        project_id:  str,
        run_id:      str,
    ) -> dict[str, Any]:
        """
        Return a single agent_run row with its steps.
        Raises 404 RUN_NOT_FOUND if not found.
        """
        result = await db.execute(
            text(
                f"SELECT id, project_id, pipeline_mode, agents_selected, status, "
                f"total_tokens, total_cost_usd, started_at, completed_at, "
                f"error_message, created_at "
                f'FROM "{schema_name}".agent_runs '
                f"WHERE id = :id AND project_id = :pid"
            ),
            {"id": run_id, "pid": project_id},
        )
        row = result.mappings().fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error":   "RUN_NOT_FOUND",
                    "message": "No agent run found with the given ID.",
                },
            )

        steps_result = await db.execute(
            text(
                f"SELECT id, run_id, agent_type, status, progress_pct, progress_label, "
                f"tokens_used, started_at, completed_at, error_message "
                f'FROM "{schema_name}".agent_run_steps '
                f"WHERE run_id = :run_id "
                f"ORDER BY agent_type"
            ),
            {"run_id": run_id},
        )
        steps = [dict(s) for s in steps_result.mappings().fetchall()]

        run = dict(row)
        run["steps"] = steps
        return run

    async def list_runs(
        self,
        db:          AsyncSession,
        schema_name: str,
        project_id:  str,
    ) -> list[dict[str, Any]]:
        """Return the latest 20 agent_runs for the project (newest first)."""
        result = await db.execute(
            text(
                f"SELECT id, project_id, pipeline_mode, agents_selected, status, "
                f"total_tokens, total_cost_usd, started_at, completed_at, "
                f"error_message, created_at "
                f'FROM "{schema_name}".agent_runs '
                f"WHERE project_id = :pid "
                f"ORDER BY created_at DESC LIMIT 20"
            ),
            {"pid": project_id},
        )
        return [dict(row) for row in result.mappings().fetchall()]


# Module-level singleton
agent_run_service = AgentRunService()
