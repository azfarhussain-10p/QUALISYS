"""
Unit tests — AgentRunService (Story 2-6)
DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.

Mocks:
  - AsyncSession (mock_db) — no real DB required
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.services.agent_run_service import AgentRunService, AGENT_DEFINITIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db(run_row=None, steps_rows=None):
    """Return a mock AsyncSession with configurable execute results."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        result = MagicMock()
        mappings = MagicMock()
        s = str(stmt).lower()

        if "order by created_at desc limit 20" in s:
            mappings.fetchall.return_value = []
            result.mappings.return_value = mappings
        elif "agent_run_steps" in s and "where run_id" in s:
            mappings.fetchall.return_value = steps_rows or []
            result.mappings.return_value = mappings
        elif "select id" in s or ("select" in s and "agent_runs" in s and "where id" in s):
            mappings.fetchone.return_value = run_row
            result.mappings.return_value = mappings
        else:
            mappings.fetchone.return_value = None
            mappings.fetchall.return_value = []
            result.mappings.return_value = mappings

        return result

    mock_db.execute = mock_execute
    return mock_db


def _make_run_row(run_id=None, project_id=None, status="queued"):
    now = "2026-02-28T00:00:00+00:00"
    return {
        "id":              run_id or str(uuid.uuid4()),
        "project_id":      project_id or str(uuid.uuid4()),
        "pipeline_mode":   "sequential",
        "agents_selected": ["ba_consultant"],
        "status":          status,
        "total_tokens":    0,
        "total_cost_usd":  0.0,
        "started_at":      None,
        "completed_at":    None,
        "error_message":   None,
        "created_at":      now,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAgentRunService:

    def test_list_agents_returns_3_agents(self):
        # Proves: list_agents() returns exactly 3 agent definitions from AGENT_DEFINITIONS.
        svc = AgentRunService()
        result = svc.list_agents()

        assert len(result) == 3
        types = {a["agent_type"] for a in result}
        assert types == {"ba_consultant", "qa_consultant", "automation_consultant"}
        # Each agent must have the required fields
        for agent in result:
            assert "name" in agent
            assert "description" in agent
            assert "icon" in agent
            assert "required_inputs" in agent
            assert "expected_outputs" in agent

    @pytest.mark.asyncio
    async def test_create_run_inserts_queued_run(self):
        # Proves: create_run with valid agents → INSERT executed, status='queued', commit called once.
        svc = AgentRunService()
        mock_db = _make_mock_db()

        result = await svc.create_run(
            db=mock_db,
            schema_name="tenant_test",
            project_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            agents_selected=["ba_consultant"],
        )

        assert result["status"] == "queued"
        assert result["pipeline_mode"] == "sequential"
        assert result["agents_selected"] == ["ba_consultant"]
        assert result["total_tokens"] == 0
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_run_inserts_steps_per_agent(self):
        # Proves: create_run with 2 agents → 3 execute calls (1 run INSERT + 2 step INSERTs).
        svc = AgentRunService()
        mock_db = _make_mock_db()
        execute_calls = []

        async def capturing_execute(stmt, *args, **kwargs):
            execute_calls.append(str(stmt).lower())
            result = MagicMock()
            result.mappings.return_value = MagicMock()
            return result

        mock_db.execute = capturing_execute

        await svc.create_run(
            db=mock_db,
            schema_name="tenant_test",
            project_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            agents_selected=["ba_consultant", "qa_consultant"],
        )

        # 1 agent_runs INSERT + 2 agent_run_steps INSERTs
        assert len(execute_calls) == 3
        assert any("agent_runs" in c for c in execute_calls)
        step_inserts = [c for c in execute_calls if "agent_run_steps" in c]
        assert len(step_inserts) == 2

    @pytest.mark.asyncio
    async def test_create_run_empty_agents_raises_400(self):
        # Proves: empty agents_selected list → raises HTTP 400 NO_AGENTS_SELECTED.
        svc = AgentRunService()
        mock_db = _make_mock_db()

        with pytest.raises(HTTPException) as exc_info:
            await svc.create_run(
                db=mock_db,
                schema_name="tenant_test",
                project_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                agents_selected=[],
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "NO_AGENTS_SELECTED"

    @pytest.mark.asyncio
    async def test_create_run_invalid_agent_raises_400(self):
        # Proves: unknown agent_type in selection → raises HTTP 400 INVALID_AGENT_TYPE.
        svc = AgentRunService()
        mock_db = _make_mock_db()

        with pytest.raises(HTTPException) as exc_info:
            await svc.create_run(
                db=mock_db,
                schema_name="tenant_test",
                project_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                agents_selected=["unknown_agent"],
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "INVALID_AGENT_TYPE"
        assert "unknown_agent" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_get_run_returns_dict(self):
        # Proves: existing run row returned as dict including steps list.
        svc = AgentRunService()
        rid = str(uuid.uuid4())
        pid = str(uuid.uuid4())
        row = _make_run_row(run_id=rid, project_id=pid, status="completed")
        mock_db = _make_mock_db(run_row=row, steps_rows=[])

        result = await svc.get_run(
            db=mock_db,
            schema_name="tenant_test",
            project_id=pid,
            run_id=rid,
        )

        assert result["id"] == rid
        assert result["status"] == "completed"
        assert "steps" in result

    @pytest.mark.asyncio
    async def test_get_run_raises_404(self):
        # Proves: missing agent run → raises HTTP 404 RUN_NOT_FOUND.
        svc = AgentRunService()
        mock_db = _make_mock_db(run_row=None)

        with pytest.raises(HTTPException) as exc_info:
            await svc.get_run(
                db=mock_db,
                schema_name="tenant_test",
                project_id=str(uuid.uuid4()),
                run_id=str(uuid.uuid4()),
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"] == "RUN_NOT_FOUND"
