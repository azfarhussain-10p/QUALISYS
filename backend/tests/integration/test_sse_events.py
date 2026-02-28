"""
Integration tests — SSE Events endpoint (Story 2-9, Task 6.1, AC-19)
DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.

Tests mock:
  - DB session (get_db override) — no real DB required
  - SSEManager (pre-populated asyncio.Queue) — no real orchestrator needed
  - Redis not required here (no POST /agent-runs in these tests)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.db import get_db
from src.main import app
from src.services.token_service import token_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str = "owner") -> str:
    return token_service.create_access_token(
        user_id=user_id,
        email=f"{role}@test.com",
        tenant_id=tenant_id,
        role=role,
        tenant_slug="test-org",
    )


def _setup_db_session(
    user_id:    uuid.UUID,
    tenant_id:  uuid.UUID,
    run_id:     uuid.UUID | None = None,
    run_exists: bool = True,
    role:       str = "owner",
):
    """Mock DB session that handles tenant auth + agent_runs lookup for SSE endpoint."""
    from src.models.user import User
    from src.models.tenant import Tenant, TenantUser

    mock_user            = MagicMock(spec=User)
    mock_user.id         = user_id
    mock_user.email      = f"{role}@test.com"

    mock_tenant          = MagicMock(spec=Tenant)
    mock_tenant.id       = tenant_id
    mock_tenant.slug     = "test-org"

    mock_membership            = MagicMock(spec=TenantUser)
    mock_membership.role       = role
    mock_membership.is_active  = True
    mock_membership.tenant_id  = tenant_id
    mock_membership.user_id    = user_id

    mock_session         = AsyncMock()
    mock_session.commit  = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        result = MagicMock()
        s = str(stmt).lower()

        if "public.tenants_users" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "public.users" in s and "public.tenants" not in s:
            result.scalar_one_or_none.return_value = mock_user
        elif "public.tenants" in s:
            result.scalar_one_or_none.return_value = mock_tenant
        elif "agent_runs" in s and "select id" in s:
            # SSE endpoint: SELECT id FROM "tenant_...".agent_runs WHERE id = :run_id
            result.scalar_one_or_none.return_value = str(run_id) if run_exists else None
        else:
            result.scalar_one_or_none.return_value = None

        return result

    mock_session.execute = mock_execute

    async def get_db_override():
        yield mock_session

    return get_db_override


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSSEEventsEndpoint:

    @pytest.mark.asyncio
    async def test_sse_endpoint_404_unknown_run(self):
        # Proves: GET /events/agent-runs/{unknown_id} returns 404 with error=RUN_NOT_FOUND
        user_id   = uuid.uuid4()
        tenant_id = uuid.uuid4()
        run_id    = uuid.uuid4()
        token = _make_token(user_id, tenant_id)

        get_db_override = _setup_db_session(
            user_id, tenant_id, run_id=run_id, run_exists=False
        )
        app.dependency_overrides[get_db] = get_db_override
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                resp = await c.get(
                    f"/api/v1/events/agent-runs/{run_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "RUN_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_sse_endpoint_200_known_run(self):
        # Proves: GET /events/agent-runs/{known_id} returns 200 StreamingResponse with Content-Type text/event-stream
        user_id   = uuid.uuid4()
        tenant_id = uuid.uuid4()
        run_id    = uuid.uuid4()
        token = _make_token(user_id, tenant_id)

        # Pre-populate queue with terminating all_done event so stream closes immediately
        q: asyncio.Queue = asyncio.Queue()
        await q.put({
            "type":    "complete",
            "payload": {"run_id": str(run_id), "all_done": True},
        })

        get_db_override = _setup_db_session(
            user_id, tenant_id, run_id=run_id, run_exists=True
        )
        app.dependency_overrides[get_db] = get_db_override
        try:
            with patch("src.api.v1.events.router.sse_manager") as mock_sse_manager:
                mock_sse_manager.get_or_create_queue.return_value = q
                mock_sse_manager.remove_queue = MagicMock()

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    async with c.stream(
                        "GET",
                        f"/api/v1/events/agent-runs/{run_id}",
                        headers={"Authorization": f"Bearer {token}"},
                    ) as resp:
                        assert resp.status_code == 200
                        content_type = resp.headers.get("content-type", "")
                        assert "text/event-stream" in content_type
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_sse_endpoint_events_sequence(self):
        # Proves: SSE stream emits events in correct order (running → complete step → complete all_done)
        user_id   = uuid.uuid4()
        tenant_id = uuid.uuid4()
        run_id    = uuid.uuid4()
        step_id   = str(uuid.uuid4())
        artifact_id = str(uuid.uuid4())
        token = _make_token(user_id, tenant_id)

        # Pre-populate queue: running → complete (step) → complete (all_done = stream terminator)
        q: asyncio.Queue = asyncio.Queue()
        await q.put({
            "type":    "running",
            "payload": {
                "step_id":        step_id,
                "agent_type":     "ba_consultant",
                "progress_pct":   0,
                "progress_label": "Agent ba_consultant is analyzing your project...",
            },
        })
        await q.put({
            "type":    "complete",
            "payload": {
                "step_id":     step_id,
                "agent_type":  "ba_consultant",
                "tokens_used": 150,
                "artifact_id": artifact_id,
            },
        })
        await q.put({
            "type":    "complete",
            "payload": {"run_id": str(run_id), "all_done": True},
        })

        get_db_override = _setup_db_session(
            user_id, tenant_id, run_id=run_id, run_exists=True
        )
        app.dependency_overrides[get_db] = get_db_override
        received_data_lines: list[str] = []
        try:
            with patch("src.api.v1.events.router.sse_manager") as mock_sse_manager:
                mock_sse_manager.get_or_create_queue.return_value = q
                mock_sse_manager.remove_queue = MagicMock()

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    async with c.stream(
                        "GET",
                        f"/api/v1/events/agent-runs/{run_id}",
                        headers={"Authorization": f"Bearer {token}"},
                    ) as resp:
                        assert resp.status_code == 200
                        async for line in resp.aiter_lines():
                            if line.startswith("data:"):
                                received_data_lines.append(line)
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert len(received_data_lines) >= 3, (
            f"Expected at least 3 data lines, got {len(received_data_lines)}: {received_data_lines}"
        )

        events = [json.loads(line.removeprefix("data: ")) for line in received_data_lines]
        event_types = [e["type"] for e in events]

        # Sequence: first event is running, last is complete+all_done
        assert event_types[0] == "running", f"First event should be 'running', got {event_types[0]!r}"
        assert "complete" in event_types, "Expected at least one 'complete' event"

        last_event = events[-1]
        assert last_event["type"] == "complete"
        assert last_event["payload"].get("all_done") is True

        # Payload structure: running event must have step_id and agent_type
        running_event = events[0]
        assert running_event["payload"]["step_id"] == step_id
        assert running_event["payload"]["agent_type"] == "ba_consultant"
        assert running_event["payload"]["progress_pct"] == 0

    @pytest.mark.asyncio
    async def test_sse_pipeline_failure_terminates_stream(self):
        # Proves: pipeline failure (error=True in all_done payload) closes stream and error flag is set
        user_id   = uuid.uuid4()
        tenant_id = uuid.uuid4()
        run_id    = uuid.uuid4()
        step_id   = str(uuid.uuid4())
        token = _make_token(user_id, tenant_id)

        # Simulate: step error → run-level complete+all_done+error=True (M-1 fix path)
        q: asyncio.Queue = asyncio.Queue()
        await q.put({
            "type":    "error",
            "payload": {
                "step_id":    step_id,
                "agent_type": "ba_consultant",
                "error_code": "STEP_FAILED",
                "message":    "Token budget exceeded",
            },
        })
        await q.put({
            "type":    "complete",
            "payload": {"run_id": str(run_id), "all_done": True, "error": True},
        })

        get_db_override = _setup_db_session(
            user_id, tenant_id, run_id=run_id, run_exists=True
        )
        app.dependency_overrides[get_db] = get_db_override
        received_data_lines: list[str] = []
        try:
            with patch("src.api.v1.events.router.sse_manager") as mock_sse_manager:
                mock_sse_manager.get_or_create_queue.return_value = q
                mock_sse_manager.remove_queue = MagicMock()

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    async with c.stream(
                        "GET",
                        f"/api/v1/events/agent-runs/{run_id}",
                        headers={"Authorization": f"Bearer {token}"},
                    ) as resp:
                        assert resp.status_code == 200
                        async for line in resp.aiter_lines():
                            if line.startswith("data:"):
                                received_data_lines.append(line)
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert len(received_data_lines) == 2, (
            f"Expected exactly 2 data lines (error + complete), got {len(received_data_lines)}"
        )

        events = [json.loads(line.removeprefix("data: ")) for line in received_data_lines]

        # First event is step-level error
        assert events[0]["type"] == "error"
        assert events[0]["payload"]["error_code"] == "STEP_FAILED"
        assert events[0]["payload"]["agent_type"] == "ba_consultant"

        # Last event is run-level complete+all_done+error — stream terminates here
        assert events[1]["type"] == "complete"
        assert events[1]["payload"]["all_done"] is True
        assert events[1]["payload"]["error"] is True
