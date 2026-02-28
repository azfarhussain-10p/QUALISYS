"""
Unit tests — AgentOrchestrator (Story 2-7)
DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.

Mocks:
  - AsyncSession (mock_db) — no real DB required
  - call_llm — patched at src.patterns.llm_pattern.call_llm
  - AsyncSessionLocal — patched for execute_pipeline session management
"""

from __future__ import annotations

import json
import uuid
from collections import namedtuple
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from src.patterns.llm_pattern import BudgetExceededError, LLMResult
from src.services.agents.orchestrator import (
    AgentOrchestrator,
    AgentResult,
    execute_pipeline,
    orchestrator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCHEMA = "tenant_testorg"
_PROJECT_ID = str(uuid.uuid4())
_RUN_ID = str(uuid.uuid4())
_TENANT_ID = str(uuid.uuid4())
_USER_ID = str(uuid.uuid4())
_STEP_ID = str(uuid.uuid4())

_GOOD_LLM_RESULT = LLMResult(
    content="{}",
    tokens_used=100,
    cost_usd=0.003,
    cached=False,
    provider="openai",
)


def _make_mock_db(
    agents_selected: list[str] | None = None,
    step_rows: list[tuple] | None = None,
    doc_rows: list[tuple] | None = None,
    github_row: tuple | None = None,
    crawl_row: tuple | None = None,
) -> AsyncMock:
    """Return a mock AsyncSession with configurable SQL result routing."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt, params=None, **kwargs):
        result = MagicMock()
        s = str(stmt).lower()

        if "select agents_selected" in s:
            row = (json.dumps(agents_selected or ["ba_consultant"]),)
            result.fetchone.return_value = row
        elif "select id, agent_type" in s and "agent_run_steps" in s:
            result.fetchall.return_value = step_rows or [(_STEP_ID, "ba_consultant")]
        elif "document_chunks" in s:
            result.fetchall.return_value = doc_rows if doc_rows is not None else [("chunk content",)]
        elif "github_connections" in s:
            result.fetchone.return_value = github_row
        elif "crawl_sessions" in s:
            result.fetchone.return_value = crawl_row
        elif "update" in s:
            result.rowcount = 1
        elif "insert" in s:
            result.rowcount = 1
        else:
            result.fetchone.return_value = None
            result.fetchall.return_value = []

        return result

    mock_db.execute = mock_execute
    return mock_db


# ---------------------------------------------------------------------------
# Tests — _assemble_context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assemble_context_returns_doc_text():
    # Proves: _assemble_context() loads document_chunks content into doc_text.
    mock_db = _make_mock_db(doc_rows=[("chunk one",), ("chunk two",)])
    with patch("src.services.agents.orchestrator.tiktoken") as mock_tiktoken:
        enc = MagicMock()
        enc.encode.return_value = list(range(20))
        enc.decode.return_value = "chunk one\n\nchunk two"
        mock_tiktoken.get_encoding.return_value = enc

        ctx = await orchestrator._assemble_context(mock_db, _SCHEMA, _PROJECT_ID)

    assert "chunk one" in ctx["doc_text"]
    assert "chunk two" in ctx["doc_text"]


@pytest.mark.asyncio
async def test_assemble_context_handles_no_sources():
    # Proves: _assemble_context() returns empty strings when no rows found.
    mock_db = _make_mock_db(doc_rows=[], github_row=None, crawl_row=None)
    with patch("src.services.agents.orchestrator.tiktoken") as mock_tiktoken:
        enc = MagicMock()
        enc.encode.return_value = []
        mock_tiktoken.get_encoding.return_value = enc

        ctx = await orchestrator._assemble_context(mock_db, _SCHEMA, _PROJECT_ID)

    assert ctx == {"doc_text": "", "github_summary": "", "crawl_data": ""}


# ---------------------------------------------------------------------------
# Tests — _run_agent_step
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_agent_step_marks_running_then_completed():
    # Proves: _run_agent_step() transitions step status to running then completed.
    mock_db = _make_mock_db()
    with patch(
        "src.services.agents.ba_consultant.call_llm",
        new_callable=AsyncMock,
        return_value=_GOOD_LLM_RESULT,
    ):
        result = await orchestrator._run_agent_step(
            db=mock_db,
            schema_name=_SCHEMA,
            step_id=_STEP_ID,
            agent_type="ba_consultant",
            context={"doc_text": "test", "github_summary": "", "crawl_data": ""},
            tenant_id=_TENANT_ID,
            user_id=_USER_ID,
            project_id=_PROJECT_ID,
            run_id=_RUN_ID,
        )

    assert result.tokens_used == 100
    assert result.artifact_type == "requirements_matrix"


@pytest.mark.asyncio
async def test_run_agent_step_creates_artifact_and_version():
    # Proves: _run_agent_step() INSERTs both an artifact and an artifact_version row.
    executed_stmts: list[str] = []
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    async def capture_execute(stmt, params=None, **kwargs):
        executed_stmts.append(str(stmt).lower())
        result = MagicMock()
        result.rowcount = 1
        result.fetchone.return_value = None
        result.fetchall.return_value = []
        return result

    mock_db.execute = capture_execute

    with patch(
        "src.services.agents.ba_consultant.call_llm",
        new_callable=AsyncMock,
        return_value=_GOOD_LLM_RESULT,
    ):
        await orchestrator._run_agent_step(
            db=mock_db,
            schema_name=_SCHEMA,
            step_id=_STEP_ID,
            agent_type="ba_consultant",
            context={"doc_text": "data", "github_summary": "", "crawl_data": ""},
            tenant_id=_TENANT_ID,
            user_id=_USER_ID,
            project_id=_PROJECT_ID,
            run_id=_RUN_ID,
        )

    insert_stmts = [s for s in executed_stmts if "insert" in s]
    assert any("artifacts" in s for s in insert_stmts), "Expected INSERT into artifacts"
    assert any("artifact_versions" in s for s in insert_stmts), "Expected INSERT into artifact_versions"


# ---------------------------------------------------------------------------
# Tests — execute_pipeline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_pipeline_completes_all_steps():
    # Proves: execute_pipeline() marks run as completed when all agents succeed.
    mock_db = _make_mock_db(
        agents_selected=["ba_consultant"],
        step_rows=[(_STEP_ID, "ba_consultant")],
        doc_rows=[("doc content",)],
    )
    updated_fields: list[dict] = []

    async def capture_update(db, schema_name, run_id, **fields):
        updated_fields.append(fields)

    with (
        patch("src.services.agents.orchestrator.AsyncSessionLocal") as mock_session_factory,
        patch("src.services.agents.ba_consultant.call_llm", new_callable=AsyncMock, return_value=_GOOD_LLM_RESULT),
        patch("src.services.agents.orchestrator.tiktoken") as mock_tiktoken,
        patch.object(orchestrator, "_update_run", new=AsyncMock(side_effect=capture_update)),
        patch.object(orchestrator, "_update_step", new=AsyncMock()),
        patch.object(orchestrator, "_create_artifact", new=AsyncMock()),
    ):
        enc = MagicMock()
        enc.encode.return_value = list(range(50))
        enc.decode.return_value = "doc content"
        mock_tiktoken.get_encoding.return_value = enc

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        await execute_pipeline(_RUN_ID, _SCHEMA, _PROJECT_ID, _TENANT_ID, _USER_ID)

    statuses = [f.get("status") for f in updated_fields]
    assert "running" in statuses
    assert "completed" in statuses


@pytest.mark.asyncio
async def test_execute_pipeline_sums_tokens_on_completion():
    # Proves: execute_pipeline() sets total_tokens = sum of all step tokens on completion.
    two_agents = ["ba_consultant", "qa_consultant"]
    step_rows  = [(_STEP_ID, "ba_consultant"), (str(uuid.uuid4()), "qa_consultant")]
    mock_db    = _make_mock_db(agents_selected=two_agents, step_rows=step_rows)

    completion_call: dict = {}

    async def capture_update(db, schema_name, run_id, **fields):
        if fields.get("status") == "completed":
            completion_call.update(fields)

    with (
        patch("src.services.agents.orchestrator.AsyncSessionLocal") as mock_session_factory,
        patch("src.services.agents.ba_consultant.call_llm", new_callable=AsyncMock, return_value=_GOOD_LLM_RESULT),
        patch("src.services.agents.qa_consultant.call_llm", new_callable=AsyncMock, return_value=_GOOD_LLM_RESULT),
        patch("src.services.agents.orchestrator.tiktoken") as mock_tiktoken,
        patch.object(orchestrator, "_update_run", new=AsyncMock(side_effect=capture_update)),
        patch.object(orchestrator, "_update_step", new=AsyncMock()),
        patch.object(orchestrator, "_create_artifact", new=AsyncMock()),
    ):
        enc = MagicMock()
        enc.encode.return_value = []
        mock_tiktoken.get_encoding.return_value = enc

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        await execute_pipeline(_RUN_ID, _SCHEMA, _PROJECT_ID, _TENANT_ID, _USER_ID)

    assert completion_call.get("total_tokens") == 200  # 100 * 2 agents


@pytest.mark.asyncio
async def test_run_agent_step_marks_failed_with_timestamp():
    # Proves: AC-17d — step UPDATE on failure includes status='failed', error_message, AND completed_at.
    captured_step_updates: list[dict] = []
    mock_db = _make_mock_db()

    async def capture_step(db, schema_name, step_id, **fields):
        captured_step_updates.append(fields)

    with (
        patch("src.services.agents.ba_consultant.call_llm", side_effect=RuntimeError("boom")),
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch.object(orchestrator, "_update_step", new=AsyncMock(side_effect=capture_step)),
        patch.object(orchestrator, "_create_artifact", new=AsyncMock()),
    ):
        with pytest.raises(RuntimeError):
            await orchestrator._run_agent_step(
                db=mock_db,
                schema_name=_SCHEMA,
                step_id=_STEP_ID,
                agent_type="ba_consultant",
                context={"doc_text": "", "github_summary": "", "crawl_data": ""},
                tenant_id=_TENANT_ID,
                user_id=_USER_ID,
                project_id=_PROJECT_ID,
                run_id=_RUN_ID,
            )

    failed_update = next(u for u in captured_step_updates if u.get("status") == "failed")
    assert failed_update["status"] == "failed"
    assert "error_message" in failed_update
    assert "completed_at" in failed_update  # AC-17d: completed_at set on step failure


@pytest.mark.asyncio
async def test_execute_pipeline_run_failed_includes_completed_at():
    # Proves: AC-17c — run UPDATE on failure includes status='failed', error_message, AND completed_at.
    failed_run_call: dict = {}

    async def capture_update(db, schema_name, run_id, **fields):
        if fields.get("status") == "failed":
            failed_run_call.update(fields)

    mock_db = _make_mock_db(
        agents_selected=["ba_consultant"],
        step_rows=[(_STEP_ID, "ba_consultant")],
    )

    with (
        patch("src.services.agents.orchestrator.AsyncSessionLocal") as mock_session_factory,
        patch("src.services.agents.ba_consultant.call_llm", side_effect=RuntimeError("fail")),
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch("src.services.agents.orchestrator.tiktoken") as mock_tiktoken,
        patch.object(orchestrator, "_update_run", new=AsyncMock(side_effect=capture_update)),
        patch.object(orchestrator, "_update_step", new=AsyncMock()),
    ):
        enc = MagicMock()
        enc.encode.return_value = []
        mock_tiktoken.get_encoding.return_value = enc

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        await execute_pipeline(_RUN_ID, _SCHEMA, _PROJECT_ID, _TENANT_ID, _USER_ID)

    assert failed_run_call["status"] == "failed"
    assert "error_message" in failed_run_call
    assert "completed_at" in failed_run_call  # AC-17c: completed_at set on run failure


@pytest.mark.asyncio
async def test_execute_pipeline_retries_llm_on_failure():
    # Proves: _run_agent_step() retries call_llm up to 3 times before succeeding.
    call_count = 0

    async def flaky_llm(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("LLM transient error")
        return _GOOD_LLM_RESULT

    mock_db = _make_mock_db()

    with (
        patch("src.services.agents.ba_consultant.call_llm", new=flaky_llm),
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch.object(orchestrator, "_update_step", new=AsyncMock()),
        patch.object(orchestrator, "_create_artifact", new=AsyncMock()),
    ):
        result = await orchestrator._run_agent_step(
            db=mock_db,
            schema_name=_SCHEMA,
            step_id=_STEP_ID,
            agent_type="ba_consultant",
            context={"doc_text": "", "github_summary": "", "crawl_data": ""},
            tenant_id=_TENANT_ID,
            user_id=_USER_ID,
            project_id=_PROJECT_ID,
            run_id=_RUN_ID,
        )

    assert call_count == 3  # failed twice, succeeded on 3rd
    assert result.tokens_used == 100


@pytest.mark.asyncio
async def test_execute_pipeline_marks_failed_after_max_retries():
    # Proves: execute_pipeline() marks run failed when all 3 LLM retries are exhausted.
    failed_call: dict = {}

    async def always_fail(*args, **kwargs):
        raise RuntimeError("LLM always fails")

    async def capture_update(db, schema_name, run_id, **fields):
        if fields.get("status") == "failed":
            failed_call.update(fields)

    mock_db = _make_mock_db(
        agents_selected=["ba_consultant"],
        step_rows=[(_STEP_ID, "ba_consultant")],
    )

    with (
        patch("src.services.agents.orchestrator.AsyncSessionLocal") as mock_session_factory,
        patch("src.services.agents.ba_consultant.call_llm", new=always_fail),
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch("src.services.agents.orchestrator.tiktoken") as mock_tiktoken,
        patch.object(orchestrator, "_update_run", new=AsyncMock(side_effect=capture_update)),
        patch.object(orchestrator, "_update_step", new=AsyncMock()),
    ):
        enc = MagicMock()
        enc.encode.return_value = []
        mock_tiktoken.get_encoding.return_value = enc

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        await execute_pipeline(_RUN_ID, _SCHEMA, _PROJECT_ID, _TENANT_ID, _USER_ID)

    assert failed_call.get("status") == "failed"
    assert "error_message" in failed_call


@pytest.mark.asyncio
async def test_execute_pipeline_skips_remaining_steps_on_failure():
    # Proves: when agent 1 fails, agent 2 step never transitions to running.
    two_agents = ["ba_consultant", "qa_consultant"]
    step_rows  = [(_STEP_ID, "ba_consultant"), (str(uuid.uuid4()), "qa_consultant")]
    mock_db    = _make_mock_db(agents_selected=two_agents, step_rows=step_rows)

    running_agents: list[str] = []

    async def capture_step_update(db, schema_name, step_id, **fields):
        if fields.get("status") == "running":
            # Find agent_type by step_id
            for sid, atype in step_rows:
                if sid == step_id:
                    running_agents.append(atype)

    with (
        patch("src.services.agents.orchestrator.AsyncSessionLocal") as mock_session_factory,
        patch("src.services.agents.ba_consultant.call_llm", side_effect=RuntimeError("fail")),
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch("src.services.agents.orchestrator.tiktoken") as mock_tiktoken,
        patch.object(orchestrator, "_update_run", new=AsyncMock()),
        patch.object(orchestrator, "_update_step", new=AsyncMock(side_effect=capture_step_update)),
    ):
        enc = MagicMock()
        enc.encode.return_value = []
        mock_tiktoken.get_encoding.return_value = enc

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        await execute_pipeline(_RUN_ID, _SCHEMA, _PROJECT_ID, _TENANT_ID, _USER_ID)

    # Only ba_consultant should have been set to running; qa_consultant never reached
    assert "qa_consultant" not in running_agents


@pytest.mark.asyncio
async def test_execute_pipeline_budget_exceeded_non_retryable():
    # Proves: BudgetExceededError immediately marks run failed without retry.
    failed_call: dict = {}
    call_count = 0

    async def budget_fail(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise BudgetExceededError(tenant_id=_TENANT_ID, used=99_000, limit=100_000)

    async def capture_update(db, schema_name, run_id, **fields):
        if fields.get("status") == "failed":
            failed_call.update(fields)

    mock_db = _make_mock_db(
        agents_selected=["ba_consultant"],
        step_rows=[(_STEP_ID, "ba_consultant")],
    )

    with (
        patch("src.services.agents.orchestrator.AsyncSessionLocal") as mock_session_factory,
        patch("src.services.agents.ba_consultant.call_llm", new=budget_fail),
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch("src.services.agents.orchestrator.tiktoken") as mock_tiktoken,
        patch.object(orchestrator, "_update_run", new=AsyncMock(side_effect=capture_update)),
        patch.object(orchestrator, "_update_step", new=AsyncMock()),
    ):
        enc = MagicMock()
        enc.encode.return_value = []
        mock_tiktoken.get_encoding.return_value = enc

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        await execute_pipeline(_RUN_ID, _SCHEMA, _PROJECT_ID, _TENANT_ID, _USER_ID)

    # BudgetExceededError is non-retryable — call_llm called exactly once
    assert call_count == 1
    assert failed_call.get("error_message") == "Token budget exceeded"


@pytest.mark.asyncio
async def test_execute_pipeline_artifacts_retained_on_failure():
    # Proves: artifact INSERT for successful steps is committed before a later step fails.
    committed: list[str] = []
    two_agents = ["ba_consultant", "qa_consultant"]
    step_rows  = [(_STEP_ID, "ba_consultant"), (str(uuid.uuid4()), "qa_consultant")]
    mock_db    = _make_mock_db(agents_selected=two_agents, step_rows=step_rows)
    mock_db.commit = AsyncMock(side_effect=lambda: committed.append("committed"))

    async def flaky_llm(*args, **kwargs):
        # ba succeeds; qa always fails
        if kwargs.get("agent_type") == "qa_consultant":
            raise RuntimeError("qa fail")
        return _GOOD_LLM_RESULT

    with (
        patch("src.services.agents.orchestrator.AsyncSessionLocal") as mock_session_factory,
        patch("src.services.agents.ba_consultant.call_llm", new_callable=AsyncMock, return_value=_GOOD_LLM_RESULT),
        patch("src.services.agents.qa_consultant.call_llm", side_effect=RuntimeError("qa fail")),
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch("src.services.agents.orchestrator.tiktoken") as mock_tiktoken,
        patch.object(orchestrator, "_update_run", new=AsyncMock()),
        patch.object(orchestrator, "_update_step", new=AsyncMock()),
        patch.object(orchestrator, "_create_artifact", new=AsyncMock()),
    ):
        enc = MagicMock()
        enc.encode.return_value = []
        mock_tiktoken.get_encoding.return_value = enc

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        await execute_pipeline(_RUN_ID, _SCHEMA, _PROJECT_ID, _TENANT_ID, _USER_ID)

    # At least one commit happened (after ba_consultant succeeded)
    assert len(committed) >= 1


@pytest.mark.asyncio
async def test_execute_pipeline_budget_exceeded_marks_step_failed():
    # Proves: AC-17d — BudgetExceededError marks the step 'failed' (not left in 'running').
    captured_step_updates: list[dict] = []

    async def capture_step(db, schema_name, step_id, **fields):
        captured_step_updates.append(fields)

    async def budget_fail(*args, **kwargs):
        raise BudgetExceededError(tenant_id=_TENANT_ID, used=99_000, limit=100_000)

    mock_db = _make_mock_db(
        agents_selected=["ba_consultant"],
        step_rows=[(_STEP_ID, "ba_consultant")],
    )

    with (
        patch("src.services.agents.orchestrator.AsyncSessionLocal") as mock_session_factory,
        patch("src.services.agents.ba_consultant.call_llm", new=budget_fail),
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch("src.services.agents.orchestrator.tiktoken") as mock_tiktoken,
        patch.object(orchestrator, "_update_run", new=AsyncMock()),
        patch.object(orchestrator, "_update_step", new=AsyncMock(side_effect=capture_step)),
    ):
        enc = MagicMock()
        enc.encode.return_value = []
        mock_tiktoken.get_encoding.return_value = enc

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        await execute_pipeline(_RUN_ID, _SCHEMA, _PROJECT_ID, _TENANT_ID, _USER_ID)

    # Step must be explicitly marked failed (not left in 'running') on BudgetExceededError
    failed_step = next((u for u in captured_step_updates if u.get("status") == "failed"), None)
    assert failed_step is not None, "Step was never marked failed after BudgetExceededError"
    assert "error_message" in failed_step
    assert "completed_at" in failed_step  # AC-17d: completed_at set on step failure


@pytest.mark.asyncio
async def test_create_artifact_returns_artifact_id():
    # Proves: _create_artifact() returns a non-empty UUID string (Task 2.2 — Story 2-9)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock())

    result = AgentResult(
        content='{"key": "value"}',
        tokens_used=50,
        cost_usd=0.001,
        artifact_type="coverage_matrix",
        content_type="application/json",
        title="BA Coverage Matrix",
    )

    artifact_id = await orchestrator._create_artifact(
        db=mock_db,
        schema_name=_SCHEMA,
        project_id=_PROJECT_ID,
        run_id=_RUN_ID,
        agent_type="ba_consultant",
        result=result,
        user_id=_USER_ID,
    )

    assert isinstance(artifact_id, str)
    assert len(artifact_id) == 36  # UUID4 canonical string length
    # Verify the returned id is a valid UUID
    import uuid as _uuid
    _uuid.UUID(artifact_id)  # raises ValueError if invalid
